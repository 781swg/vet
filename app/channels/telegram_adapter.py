from aiogram import Bot

from app.channels.base import ChannelAdapter
from app.channels.normalizer import normalize_telegram_update
from app.channels.schemas import UnifiedIncomingMessage
from app.core.config import get_settings
from app.core.logging import get_logger


logger = get_logger(__name__)


class TelegramAdapter(ChannelAdapter):
    channel = "telegram"

    def __init__(self, token: str | None = None) -> None:
        self.token = token or get_settings().telegram_client_bot_token

    def parse_webhook(self, payload: dict) -> list[UnifiedIncomingMessage]:
        message = normalize_telegram_update(payload)
        return [message] if message else []

    async def send_text(self, external_user_id: str, text: str) -> None:
        if not self.token:
            logger.info("telegram_client_token_missing", chat_id=external_user_id, text=text)
            return
        bot = Bot(self.token)
        try:
            await bot.send_message(chat_id=external_user_id, text=text)
        except Exception as exc:
            logger.exception("telegram_send_failed", chat_id=external_user_id, error=str(exc))
            raise
        finally:
            await bot.session.close()


TelegramClientSender = TelegramAdapter
