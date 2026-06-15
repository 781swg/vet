from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import WebhookEvent


class WebhookEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def register_once(self, *, channel: str, idempotency_key: str, raw_payload: dict | None = None) -> tuple[WebhookEvent, bool]:
        event = WebhookEvent(
            channel=channel,
            idempotency_key=idempotency_key,
            status="received",
            raw_payload=raw_payload or {},
            created_at=datetime.now(UTC),
        )
        self.session.add(event)
        try:
            await self.session.flush()
            return event, True
        except IntegrityError:
            await self.session.rollback()
            result = await self.session.execute(
                select(WebhookEvent).where(WebhookEvent.channel == channel, WebhookEvent.idempotency_key == idempotency_key)
            )
            return result.scalars().first(), False

    async def mark_status(self, event_id: int, status: str) -> None:
        event = await self.session.get(WebhookEvent, event_id)
        if not event:
            return
        event.status = status
        if status in {"processed", "failed"}:
            event.processed_at = datetime.now(UTC)
        await self.session.flush()

