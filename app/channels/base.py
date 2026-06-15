from abc import ABC, abstractmethod

from app.channels.schemas import UnifiedIncomingMessage, UnifiedMessage


class ChannelAdapter(ABC):
    channel: str

    @abstractmethod
    def parse_webhook(self, payload: dict) -> list[UnifiedIncomingMessage]:
        raise NotImplementedError

    @abstractmethod
    async def send_text(self, external_user_id: str, text: str) -> None:
        raise NotImplementedError


ChannelSender = ChannelAdapter
