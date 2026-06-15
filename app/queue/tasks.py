import asyncio

from app.api.routes.webhook_utils import reply_target
from app.channels.registry import channel_registry
from app.channels.schemas import UnifiedIncomingMessage
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.repositories.webhooks import WebhookEventRepository
from app.db.session import SessionLocal
from app.dialogs.manager import DialogManager


logger = get_logger(__name__)


def process_webhook_message(message_data: dict, event_id: int | None = None) -> dict:
    return asyncio.run(_process_webhook_message(message_data, event_id))


async def _process_webhook_message(message_data: dict, event_id: int | None = None) -> dict:
    message = UnifiedIncomingMessage.model_validate(message_data)
    adapter = channel_registry.get(message.channel)

    async with SessionLocal() as session:
        try:
            logger.info("message_received", channel=message.channel, message_id=message.message_id, chat_id=message.external_chat_id)
            logger.info("llm_started", channel=message.channel, message_id=message.message_id)
            result = await DialogManager(session).process_message(message)
            logger.info("llm_finished", channel=message.channel, message_id=message.message_id, lead_id=result.lead_id)
            await session.commit()
            target = reply_target(message)
            logger.info("telegram_send_started" if message.channel == "telegram" else "channel_send_started", channel=message.channel, chat_id=target, message_id=message.message_id)
            await adapter.send_text(target, result.answer)
            logger.info("telegram_send_success" if message.channel == "telegram" else "channel_send_success", channel=message.channel, chat_id=target, message_id=message.message_id)
            if event_id:
                await WebhookEventRepository(session).mark_status(event_id, "processed")
                await session.commit()
            return {"ok": True, "lead_id": result.lead_id, "need_handoff": result.need_handoff}
        except Exception as exc:
            logger.exception("webhook_message_processing_failed", channel=message.channel, message_id=message.message_id)
            await session.rollback()
            fallback_answer = await _save_failure_and_get_fallback(session, message, exc)
            await session.commit()
            try:
                target = reply_target(message)
                logger.info("telegram_send_started" if message.channel == "telegram" else "channel_send_started", channel=message.channel, chat_id=target, message_id=message.message_id, fallback=True)
                await adapter.send_text(target, fallback_answer)
                logger.info("telegram_send_success" if message.channel == "telegram" else "channel_send_success", channel=message.channel, chat_id=target, message_id=message.message_id, fallback=True)
            except Exception as send_exc:
                logger.exception("telegram_send_failed" if message.channel == "telegram" else "channel_send_failed", channel=message.channel, message_id=message.message_id, error=str(send_exc))
                await session.rollback()
                await _audit_failure(session, message, "telegram_send_error" if message.channel == "telegram" else "channel_send_error", send_exc)
                await session.commit()
            if event_id:
                await WebhookEventRepository(session).mark_status(event_id, "failed")
                await session.commit()
            return {"ok": False, "fallback_sent": True, "error": str(exc)}


async def _audit_failure(session, message: UnifiedIncomingMessage, action: str, exc: Exception) -> None:
    from app.db.repositories.crm import CRMRepository

    await CRMRepository(session).add_audit_log(
        business_id=message.business_id,
        action=action,
        payload={"channel": message.channel, "message_id": message.message_id, "error": str(exc), "text": message.text},
    )


async def _save_failure_and_get_fallback(session, message: UnifiedIncomingMessage, exc: Exception) -> str:
    from app.db.repositories.analytics import AnalyticsRepository
    from app.db.repositories.crm import CRMRepository

    settings = get_settings()
    crm = CRMRepository(session)
    analytics = AnalyticsRepository(session)
    await _audit_failure(session, message, "webhook_message_processing_failed", exc)

    channel = await crm.get_or_create_channel(message.business_id, message.channel)
    contact, _ = await crm.get_or_create_contact(message, channel)
    conversation, _ = await crm.get_or_create_conversation(message.business_id, contact.id, channel.id)
    lead = await crm.create_lead(
        business_id=message.business_id,
        contact_id=contact.id,
        conversation_id=conversation.id,
        intake_form_id=None,
        source_channel=message.channel,
        interest=message.text,
        priority="high",
    )
    await crm.create_handoff(
        business_id=message.business_id,
        conversation_id=conversation.id,
        lead_id=lead.id,
        reason="Ошибка обработки сообщения, нужен врач",
        priority="high",
    )
    await analytics.track(
        business_id=message.business_id,
        event_type="llm_error",
        channel=message.channel,
        contact_id=contact.id,
        conversation_id=conversation.id,
        lead_id=lead.id,
        payload={"error": str(exc)},
    )
    answer = (
        "Извините, сейчас я не смог корректно обработать сообщение. Я передам ваш вопрос доктору. "
        f"Если вопрос срочный — пожалуйста, позвоните по номеру {getattr(settings, 'business_phone', None) or '+899999999'}."
    )
    await crm.add_message(conversation.id, "bot", answer, llm_context={"fallback_error": str(exc)})
    return answer
