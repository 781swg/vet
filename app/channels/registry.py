from app.channels.base import ChannelAdapter
from app.channels.max_adapter import MaxAdapter
from app.channels.telegram_adapter import TelegramAdapter
from app.channels.vk_adapter import VkAdapter
from app.channels.whatsapp_adapter import WhatsAppAdapter


class ChannelRegistry:
    def __init__(self) -> None:
        self.adapters: dict[str, ChannelAdapter] = {}

    def register(self, adapter: ChannelAdapter) -> None:
        self.adapters[adapter.channel] = adapter

    def get(self, channel: str) -> ChannelAdapter:
        return self.adapters[channel]


def build_channel_registry() -> ChannelRegistry:
    registry = ChannelRegistry()
    registry.register(TelegramAdapter())
    registry.register(WhatsAppAdapter())
    registry.register(MaxAdapter())
    registry.register(VkAdapter())
    return registry


channel_registry = build_channel_registry()

