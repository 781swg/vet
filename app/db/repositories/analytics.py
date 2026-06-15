from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AnalyticsEvent


class AnalyticsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def track(
        self,
        *,
        business_id: int,
        event_type: str,
        channel: str | None = None,
        contact_id: int | None = None,
        conversation_id: int | None = None,
        lead_id: int | None = None,
        payload: dict | None = None,
    ) -> AnalyticsEvent:
        event = AnalyticsEvent(
            business_id=business_id,
            contact_id=contact_id,
            conversation_id=conversation_id,
            lead_id=lead_id,
            channel=channel,
            event_type=event_type,
            event_payload=payload or {},
            created_at=datetime.now(UTC),
        )
        self.session.add(event)
        await self.session.flush()
        return event
