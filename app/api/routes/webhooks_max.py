from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rate_limit import check_rate_limit
from app.api.routes.webhook_utils import dispatch_channel_messages
from app.channels.registry import channel_registry
from app.core.config import get_settings
from app.db.session import get_session


router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/max")
async def max_webhook(request: Request, payload: dict, session: AsyncSession = Depends(get_session)) -> dict:
    check_rate_limit(request, "max")
    settings = get_settings()
    secret = request.headers.get("X-Max-Bot-Api-Secret")
    if settings.max_webhook_secret and secret != settings.max_webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid MAX secret")

    adapter = channel_registry.get("max")
    messages = adapter.parse_webhook(payload)
    if not messages:
        return {"ok": True, "ignored": True}
    results = await dispatch_channel_messages(session=session, adapter=adapter, messages=messages)
    return {"ok": True, "results": results}
