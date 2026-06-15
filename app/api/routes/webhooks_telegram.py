from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rate_limit import check_rate_limit
from app.api.routes.webhook_utils import dispatch_channel_messages
from app.channels.registry import channel_registry
from app.db.session import get_session


router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/telegram")
async def telegram_webhook(request: Request, payload: dict, session: AsyncSession = Depends(get_session)) -> dict:
    check_rate_limit(request, "telegram")
    adapter = channel_registry.get("telegram")
    messages = adapter.parse_webhook(payload)
    if not messages:
        return {"ok": True, "ignored": True}
    results = await dispatch_channel_messages(session=session, adapter=adapter, messages=messages)
    return {"ok": True, "results": results}
