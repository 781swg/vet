from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rate_limit import check_rate_limit
from app.core.config import get_settings
from app.crm.site_leads import SiteLeadIn, create_site_lead
from app.db.session import get_session


router = APIRouter(prefix="/api/site", tags=["site"])


@router.get("/config")
async def site_config() -> dict:
    settings = get_settings()
    return {
        "clinic": {
            "name": "Вет клиника Дениса",
            "phone": "+7 (383) 271-09-01",
            "address": "ул. Богдана Хмельницкого, 39",
        },
        "telegram": {
            "client_bot_username": settings.telegram_client_bot_username,
            "client_bot_url": f"https://t.me/{settings.telegram_client_bot_username}",
            "doctor_notification_bot_username": settings.telegram_doctor_bot_username,
        },
    }


@router.post("/leads")
async def create_site_lead_endpoint(
    request: Request,
    payload: SiteLeadIn,
    session: AsyncSession = Depends(get_session),
) -> dict:
    check_rate_limit(request, "site")
    settings = get_settings()
    result = await create_site_lead(session, payload, business_id=settings.default_business_id)
    await session.commit()
    return {
        "ok": True,
        "lead_id": result.lead.id,
        "status": result.lead.status,
        "priority": result.lead.priority,
        "notification_sent": result.notification_sent,
        "telegram_bot_url": f"https://t.me/{settings.telegram_client_bot_username}",
    }
