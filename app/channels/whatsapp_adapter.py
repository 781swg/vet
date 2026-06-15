from datetime import UTC, datetime

import httpx

from app.channels.base import ChannelAdapter
from app.channels.schemas import UnifiedIncomingMessage
from app.core.config import get_settings
from app.core.logging import get_logger


logger = get_logger(__name__)


class WhatsAppAdapter(ChannelAdapter):
    channel = "whatsapp"

    def parse_webhook(self, payload: dict) -> list[UnifiedIncomingMessage]:
        settings = get_settings()
        result: list[UnifiedIncomingMessage] = []

        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                contacts_by_id = {
                    contact.get("wa_id"): contact.get("profile", {}).get("name")
                    for contact in value.get("contacts", [])
                    if contact.get("wa_id")
                }

                for msg in value.get("messages", []):
                    if msg.get("type") != "text":
                        logger.info("whatsapp_unsupported_message_type", message_type=msg.get("type"))
                        continue

                    wa_user_id = str(msg.get("from") or "")
                    text = msg.get("text", {}).get("body", "").strip()
                    if not wa_user_id or not text:
                        continue

                    timestamp = datetime.now(UTC)
                    if msg.get("timestamp"):
                        timestamp = datetime.fromtimestamp(int(msg["timestamp"]), UTC)

                    result.append(
                        UnifiedIncomingMessage(
                            channel="whatsapp",
                            business_id=settings.default_business_id,
                            external_user_id=wa_user_id,
                            external_chat_id=wa_user_id,
                            message_id=msg.get("id"),
                            text=text,
                            raw_payload=msg,
                            timestamp=timestamp,
                            display_name=contacts_by_id.get(wa_user_id),
                        )
                    )

        return result

    async def send_text(self, external_user_id: str, text: str) -> dict | None:
        settings = get_settings()
        if not settings.whatsapp_access_token or not settings.whatsapp_phone_number_id:
            logger.info("whatsapp_credentials_missing", external_user_id=external_user_id, text=text)
            return None

        url = (
            f"https://graph.facebook.com/{settings.whatsapp_api_version}/"
            f"{settings.whatsapp_phone_number_id}/messages"
        )
        payload = {
            "messaging_product": "whatsapp",
            "to": external_user_id,
            "type": "text",
            "text": {"body": text},
        }
        headers = {
            "Authorization": f"Bearer {settings.whatsapp_access_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()


WhatsAppSender = WhatsAppAdapter
