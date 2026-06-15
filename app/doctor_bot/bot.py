import asyncio

from aiogram import Bot, Dispatcher

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.doctor_bot.handlers import router


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = get_logger(__name__)
    if not settings.telegram_doctor_bot_token:
        logger.warning("doctor_bot_token_missing_waiting")
        while True:
            await asyncio.sleep(3600)
    bot = Bot(settings.telegram_doctor_bot_token)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
