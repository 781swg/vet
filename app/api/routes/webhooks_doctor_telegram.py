from aiogram import Bot, Dispatcher
from aiogram.types import Update
from fastapi import APIRouter, Request

from app.api.rate_limit import check_rate_limit
from app.core.config import get_settings
from app.core.logging import get_logger
from app.doctor_bot.handlers import router as doctor_router


router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])
logger = get_logger(__name__)

_doctor_bot: Bot | None = None
_doctor_dispatcher: Dispatcher | None = None


def get_doctor_bot_and_dispatcher() -> tuple[Bot | None, Dispatcher | None]:
    global _doctor_bot, _doctor_dispatcher
    settings = get_settings()
    if not settings.telegram_doctor_bot_token:
        return None, None
    if _doctor_bot is None:
        _doctor_bot = Bot(settings.telegram_doctor_bot_token)
    if _doctor_dispatcher is None:
        _doctor_dispatcher = Dispatcher()
        _doctor_dispatcher.include_router(doctor_router)
    return _doctor_bot, _doctor_dispatcher


@router.post("/doctor-telegram")
async def doctor_telegram_webhook(request: Request, payload: dict) -> dict:
    """Webhook endpoint for the doctor's Telegram bot.

    This replaces long polling so the project can run as one Render Web Service.
    """
    check_rate_limit(request, "doctor-telegram")
    bot, dispatcher = get_doctor_bot_and_dispatcher()
    if not bot or not dispatcher:
        logger.info("doctor_bot_token_missing_webhook_ignored")
        return {"ok": True, "ignored": True}

    update = Update.model_validate(payload, context={"bot": bot})
    await dispatcher.feed_update(bot, update)
    return {"ok": True}
