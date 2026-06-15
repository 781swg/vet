import httpx

from app.channels.base import ChannelAdapter
from app.channels.schemas import UnifiedIncomingMessage
from app.core.config import get_settings
from app.core.logging import get_logger


logger = get_logger(__name__)


class VkAdapter(ChannelAdapter):
    channel = "vk"

    def parse_webhook(self, payload: dict) -> list[UnifiedIncomingMessage]:
        settings = get_settings()
        if payload.get("type") != "message_new":
            return []
        message = payload.get("object", {}).get("message", {})
        text = (message.get("text") or "").strip()
        peer_id = str(message.get("peer_id") or message.get("from_id") or "")
        from_id = str(message.get("from_id") or peer_id)
        if not text or not from_id:
            return []
        return [
            UnifiedIncomingMessage(
                channel="vk",
                business_id=settings.default_business_id,
                external_user_id=from_id,
                external_chat_id=peer_id,
                message_id=str(message.get("id") or ""),
                text=text,
                raw_payload=payload,
            )
        ]

    async def send_text(self, external_user_id: str, text: str) -> dict | None:
        settings = get_settings()
        if not settings.vk_access_token:
            logger.info("vk_credentials_missing", external_user_id=external_user_id, text=text)
            return None
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                "https://api.vk.com/method/messages.send",
                data={
                    "access_token": settings.vk_access_token,
                    "v": "5.199",
                    "user_id": external_user_id,
                    "random_id": 0,
                    "message": text,
                },
            )
            response.raise_for_status()
            return response.json()


VkSender = VkAdapter
