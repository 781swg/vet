from datetime import UTC, datetime

from app.channels.base import UnifiedMessage


def normalize_telegram_update(payload: dict, business_id: int = 1) -> UnifiedMessage | None:
    message = payload.get("message") or payload.get("edited_message")
    if not message or "text" not in message:
        return None

    user = message.get("from") or {}
    chat = message.get("chat") or {}
    timestamp = datetime.fromtimestamp(message.get("date"), UTC) if message.get("date") else datetime.now(UTC)
    display_name = " ".join(part for part in [user.get("first_name"), user.get("last_name")] if part) or user.get("username")

    return UnifiedMessage(
        channel="telegram",
        external_user_id=str(user.get("id") or chat.get("id")),
        external_chat_id=str(chat.get("id")),
        text=message["text"].strip(),
        raw_payload=payload,
        business_id=business_id,
        timestamp=timestamp,
        username=user.get("username"),
        display_name=display_name,
    )


def normalize_stub_webhook(channel: str, payload: dict, business_id: int = 1) -> UnifiedMessage:
    return UnifiedMessage(
        channel=channel,
        external_user_id=str(payload.get("external_user_id") or payload.get("user_id") or "unknown"),
        external_chat_id=str(payload.get("external_chat_id") or payload.get("chat_id") or payload.get("external_user_id") or "unknown"),
        text=str(payload.get("text") or "").strip(),
        raw_payload=payload,
        business_id=business_id,
        username=payload.get("username"),
        display_name=payload.get("display_name") or payload.get("name"),
    )
