from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    default_business_id: int = 1
    database_url: str = "sqlite+aiosqlite:///./vet_ai_manager.db"
    public_base_url: str | None = None
    site_cors_origins: list[str] = ["*"]
    admin_api_key: str | None = None
    webhook_rate_limit_per_minute: int = 120
    redis_url: str | None = None
    queue_name: str = "webhooks"
    queue_enabled: bool = True
    token_encryption_key: str | None = None
    backup_dir: str = "./backups"
    backup_retention_days: int = 14
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str = "gpt-4o-mini"
    telegram_client_bot_token: str | None = None
    telegram_doctor_bot_token: str | None = None
    telegram_client_bot_username: str = "denisclinik_bot"
    telegram_doctor_bot_username: str = "Denis_Notification_klinila_bot"
    doctor_telegram_user_id: int | None = None
    whatsapp_access_token: str | None = None
    whatsapp_phone_number_id: str | None = None
    whatsapp_verify_token: str | None = None
    whatsapp_api_version: str = "v21.0"
    whatsapp_webhook_secret: str | None = None
    max_bot_token: str | None = None
    max_webhook_secret: str | None = None
    max_api_base_url: str = "https://platform-api.max.ru"
    vk_access_token: str | None = None
    vk_confirmation_token: str | None = None
    vk_secret: str | None = None
    business_timezone: str = "Europe/Moscow"
    app_env: str = "local"
    log_level: str = Field(default="INFO")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator(
        "openai_api_key",
        "openai_base_url",
        "telegram_client_bot_token",
        "telegram_doctor_bot_token",
        "doctor_telegram_user_id",
        "public_base_url",
        "admin_api_key",
        "redis_url",
        "token_encryption_key",
        "whatsapp_access_token",
        "whatsapp_phone_number_id",
        "whatsapp_verify_token",
        "whatsapp_webhook_secret",
        "max_bot_token",
        "max_webhook_secret",
        "vk_access_token",
        "vk_confirmation_token",
        "vk_secret",
        mode="before",
    )
    @classmethod
    def empty_string_to_none(cls, value):
        return None if value == "" else value

    @field_validator("site_cors_origins", mode="before")
    @classmethod
    def parse_site_cors_origins(cls, value):
        if isinstance(value, list):
            return value
        if value is None or value == "":
            return ["*"]
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("openai_model", mode="before")
    @classmethod
    def default_openai_model(cls, value):
        return "gpt-4o-mini" if value == "" or value is None else value

    @field_validator("whatsapp_api_version", mode="before")
    @classmethod
    def default_whatsapp_api_version(cls, value):
        return "v21.0" if value == "" or value is None else value

    @field_validator("max_api_base_url", mode="before")
    @classmethod
    def default_max_api_base_url(cls, value):
        return "https://platform-api.max.ru" if value == "" or value is None else value

    @field_validator("queue_enabled", mode="before")
    @classmethod
    def parse_queue_enabled(cls, value):
        if isinstance(value, str):
            return value.lower() not in {"0", "false", "no", "off"}
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
