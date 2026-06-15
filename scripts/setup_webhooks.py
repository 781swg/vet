import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from app.core.config import get_settings


async def set_telegram_bot_webhook(client: httpx.AsyncClient, token: str | None, webhook_url: str, label: str) -> None:
    if not token:
        print(f"Telegram {label}: token is empty, skipped")
        return
    response = await client.post(
        f"https://api.telegram.org/bot{token}/setWebhook",
        json={"url": webhook_url, "drop_pending_updates": False},
    )
    response.raise_for_status()
    print(f"Telegram {label} webhook set: {webhook_url}")


async def set_telegram_webhooks(client: httpx.AsyncClient, base_url: str) -> None:
    settings = get_settings()
    base = base_url.rstrip("/")
    await set_telegram_bot_webhook(
        client,
        settings.telegram_client_bot_token,
        f"{base}/api/webhooks/telegram",
        "client",
    )
    await set_telegram_bot_webhook(
        client,
        settings.telegram_doctor_bot_token,
        f"{base}/api/webhooks/doctor-telegram",
        "doctor",
    )


async def set_max_subscription(client: httpx.AsyncClient, base_url: str) -> None:
    settings = get_settings()
    if not settings.max_bot_token:
        print("MAX: MAX_BOT_TOKEN is empty, skipped")
        return
    payload = {
        "url": f"{base_url.rstrip('/')}/api/webhooks/max",
        "update_types": ["message_created", "bot_started"],
    }
    if settings.max_webhook_secret:
        payload["secret"] = settings.max_webhook_secret
    response = await client.post(
        f"{settings.max_api_base_url.rstrip('/')}/subscriptions",
        headers={"Authorization": settings.max_bot_token, "Content-Type": "application/json"},
        json=payload,
    )
    response.raise_for_status()
    print(f"MAX subscription set: {payload['url']}")


async def main() -> None:
    settings = get_settings()
    if not settings.public_base_url:
        raise RuntimeError("PUBLIC_BASE_URL must be set to an HTTPS URL before webhook setup")
    if not settings.public_base_url.startswith("https://"):
        raise RuntimeError("PUBLIC_BASE_URL must use HTTPS for production webhooks")

    async with httpx.AsyncClient(timeout=30) as client:
        await set_telegram_webhooks(client, settings.public_base_url)
        await set_max_subscription(client, settings.public_base_url)

    print("WhatsApp: set callback URL in Meta App dashboard:")
    print(f"{settings.public_base_url.rstrip('/')}/api/webhooks/whatsapp")
    print("VK: set callback URL in VK Callback API settings:")
    print(f"{settings.public_base_url.rstrip('/')}/api/webhooks/vk")


if __name__ == "__main__":
    asyncio.run(main())
