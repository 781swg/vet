from sqlalchemy.ext.asyncio import AsyncSession

from app.channels.base import ChannelAdapter
from app.channels.schemas import UnifiedIncomingMessage
from app.core.logging import get_logger
from app.db.repositories.webhooks import WebhookEventRepository
from app.dialogs.manager import DialogManager
from app.queue.dispatcher import enqueue_webhook_message


logger = get_logger(__name__)


def reply_target(message: UnifiedIncomingMessage) -> str:
    if message.channel == "telegram" and message.external_chat_id:
        return message.external_chat_id
    return message.external_user_id


async def process_channel_messages(
    *,
    session: AsyncSession,
    adapter: ChannelAdapter,
    messages: list[UnifiedIncomingMessage],
) -> list[dict]:
    results: list[dict] = []
    manager = DialogManager(session)
    for message in messages:
        result = await manager.process_message(message)
        await session.commit()
        await adapter.send_text(reply_target(message), result.answer)
        results.append({"message_id": message.message_id, "lead_id": result.lead_id, "need_handoff": result.need_handoff})
    return results


def idempotency_key(message: UnifiedIncomingMessage) -> str:
    if message.message_id:
        return message.message_id
    return f"{message.external_user_id}:{message.external_chat_id}:{message.timestamp.isoformat()}:{hash(message.text)}"


async def dispatch_channel_messages(
    *,
    session: AsyncSession,
    adapter: ChannelAdapter,
    messages: list[UnifiedIncomingMessage],
) -> list[dict]:
    results: list[dict] = []
    webhook_repo = WebhookEventRepository(session)
    for message in messages:
        event, created = await webhook_repo.register_once(
            channel=message.channel,
            idempotency_key=idempotency_key(message),
            raw_payload=message.raw_payload,
        )
        await session.commit()
        if not created:
            results.append({"message_id": message.message_id, "duplicate": True, "event_id": event.id if event else None})
            continue

        message_data = message.model_dump(mode="json")
        try:
            job_id = enqueue_webhook_message(message_data, event.id)
        except Exception as exc:
            logger.warning("webhook_enqueue_failed_falling_back_inline", error=str(exc), channel=message.channel)
            inline = await process_channel_messages(session=session, adapter=adapter, messages=[message])
            await webhook_repo.mark_status(event.id, "processed")
            await session.commit()
            results.extend(inline)
            continue

        if job_id:
            event.status = "queued"
            await session.commit()
            results.append({"message_id": message.message_id, "queued": True, "job_id": job_id, "event_id": event.id})
        else:
            inline = await process_channel_messages(session=session, adapter=adapter, messages=[message])
            await webhook_repo.mark_status(event.id, "processed")
            await session.commit()
            results.extend(inline)
    return results
