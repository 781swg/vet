import json
from urllib.parse import urlparse, urlunparse

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger


logger = get_logger(__name__)


def normalize_openai_base_url(base_url: str) -> str:
    parsed = urlparse(base_url.rstrip("/"))
    if parsed.netloc == "openrouter.ai" and parsed.path in {"", "/", "/models"}:
        return "https://openrouter.ai/api/v1"
    if parsed.path.endswith("/chat/completions"):
        return urlunparse(parsed._replace(path=parsed.path.removesuffix("/chat/completions")))
    return base_url.rstrip("/")


class LLMClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def complete_json(self, messages: list[dict]) -> dict | None:
        if not self.settings.openai_api_key or not self.settings.openai_base_url:
            return None
        base_url = normalize_openai_base_url(self.settings.openai_base_url)
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.settings.openai_api_key}"},
                    json={
                        "model": self.settings.openai_model,
                        "messages": messages,
                        "temperature": 0.2,
                        "response_format": {"type": "json_object"},
                    },
                )
                response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return json.loads(content)
        except Exception as exc:
            logger.warning("llm_request_failed_using_fallback", error=str(exc), base_url=base_url)
            return None
