from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rate_limit import check_rate_limit
from app.api.routes.webhook_utils import dispatch_channel_messages
from app.channels.registry import channel_registry
from app.core.config import get_settings
from app.db.session import get_session


router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.get("/whatsapp")
async def verify_whatsapp_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
) -> PlainTextResponse:
    settings = get_settings()
    if hub_mode == "subscribe" and settings.whatsapp_verify_token and hub_verify_token == settings.whatsapp_verify_token:
        return PlainTextResponse(hub_challenge)
    raise HTTPException(status_code=403, detail="Invalid verify token")


@router.post("/whatsapp")
async def whatsapp_webhook(request: Request, payload: dict, session: AsyncSession = Depends(get_session)) -> dict:
    check_rate_limit(request, "whatsapp")
    adapter = channel_registry.get("whatsapp")
    messages = adapter.parse_webhook(payload)
    if not messages:
        return {"ok": True, "ignored": True}
    results = await dispatch_channel_messages(session=session, adapter=adapter, messages=messages)
    return {"ok": True, "results": results}
