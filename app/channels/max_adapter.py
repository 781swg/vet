from datetime import UTC, datetime

import httpx

from app.channels.base import ChannelAdapter
from app.channels.schemas import UnifiedIncomingMessage
from app.core.config import get_settings
from app.core.logging import get_logger


logger = get_logger(__name__)


class MaxAdapter(ChannelAdapter):
    channel = "max"

    def parse_webhook(self, payload: dict) -> list[UnifiedIncomingMessage]:
        settings = get_settings()
        update_type = payload.get("update_type") or payload.get("type")
        if update_type != "message_created":
            return []

        message = payload.get("message", {})
        body = message.get("body", {})
        text = (body.get("text") or message.get("text") or "").strip()
        if not text:
            return []

        sender = message.get("sender") or message.get("from") or {}
        recipient = message.get("recipient") or message.get("chat") or {}
        external_user_id = str(sender.get("user_id") or sender.get("id") or "")
        external_chat_id = str(recipient.get("chat_id") or recipient.get("id") or external_user_id)
        if not external_user_id:
            return []

        timestamp = datetime.now(UTC)
        raw_ts = message.get("timestamp") or message.get("created_at")
        if isinstance(raw_ts, (int, float)):
            timestamp = datetime.fromtimestamp(raw_ts / 1000 if raw_ts > 10_000_000_000 else raw_ts, UTC)

        display_name = sender.get("name") or sender.get("first_name") or sender.get("username")

        return [
            UnifiedIncomingMessage(
                channel="max",
                business_id=settings.default_business_id,
                external_user_id=external_user_id,
                external_chat_id=external_chat_id,
                message_id=str(message.get("mid") or message.get("id") or ""),
                text=text,
                raw_payload=payload,
                timestamp=timestamp,
                username=sender.get("username"),
                display_name=display_name,
            )
        ]

    async def send_text(self, external_user_id: str, text: str) -> dict | None:
        settings = get_settings()
        if not settings.max_bot_token:
            logger.info("max_credentials_missing", external_user_id=external_user_id, text=text)
            return None

        url = f"{settings.max_api_base_url.rstrip('/')}/messages"
        headers = {
            "Authorization": settings.max_bot_token,
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(url, params={"user_id": external_user_id}, json={"text": text}, headers=headers)
            response.raise_for_status()
            return response.json()


MaxSender = MaxAdapter
