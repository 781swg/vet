from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


ChannelName = Literal["telegram", "whatsapp", "max", "vk", "site"]


class UnifiedIncomingMessage(BaseModel):
    channel: ChannelName
    external_user_id: str
    external_chat_id: str | None = None
    message_id: str | None = None
    text: str
    raw_payload: dict = Field(default_factory=dict)
    business_id: int = 1
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    username: str | None = None
    display_name: str | None = None
    source: str | None = None


UnifiedMessage = UnifiedIncomingMessage
