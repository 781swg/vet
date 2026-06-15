from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rate_limit import check_rate_limit
from app.api.routes.webhook_utils import dispatch_channel_messages
from app.channels.registry import channel_registry
from app.core.config import get_settings
from app.db.session import get_session


router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/vk")
async def vk_webhook(request: Request, payload: dict, session: AsyncSession = Depends(get_session)):
    check_rate_limit(request, "vk")
    settings = get_settings()
    if payload.get("type") == "confirmation":
        if not settings.vk_confirmation_token:
            raise HTTPException(status_code=500, detail="VK confirmation token is not configured")
        return PlainTextResponse(settings.vk_confirmation_token)

    if settings.vk_secret and request.headers.get("X-VK-Signature") != settings.vk_secret and payload.get("secret") != settings.vk_secret:
        raise HTTPException(status_code=403, detail="Invalid VK secret")

    adapter = channel_registry.get("vk")
    messages = adapter.parse_webhook(payload)
    if not messages:
        return {"ok": True, "ignored": True}
    await dispatch_channel_messages(session=session, adapter=adapter, messages=messages)
    return PlainTextResponse("ok")
