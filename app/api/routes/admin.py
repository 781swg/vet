from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_admin_api_key
from app.core.tokens import encrypt_token
from app.db.models import AnimalType, Channel, Contact, ContactChannelAccount, Message, Price, Service
from app.db.repositories.catalog import CatalogRepository
from app.db.repositories.crm import CRMRepository
from app.db.session import get_session
from app.reports.generator import ReportGenerator


router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin_api_key)])


class ServiceIn(BaseModel):
    name: str
    category: str | None = None
    description: str | None = None
    is_active: bool = True
    requires_doctor_confirmation: bool = True


class PriceIn(BaseModel):
    service_id: int
    price_from: float | None = None
    price_to: float | None = None
    currency: str = "RUB"
    comment: str | None = None
    is_active: bool = True


class ServiceUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    description: str | None = None
    is_active: bool | None = None
    requires_doctor_confirmation: bool | None = None


class AnimalTypeUpdate(BaseModel):
    name: str | None = None
    is_supported: bool | None = None
    comment: str | None = None


class LeadStatusIn(BaseModel):
    status: str


class ChannelTokenIn(BaseModel):
    channel_type: str
    token: str | None = None
    token_ref: str | None = None


@router.get("/services")
async def list_services(session: AsyncSession = Depends(get_session)) -> list[dict]:
    services = await CatalogRepository(session).list_services()
    return [{"id": item.id, "name": item.name, "category": item.category, "description": item.description, "is_active": item.is_active} for item in services]


@router.post("/services")
async def create_service(data: ServiceIn, session: AsyncSession = Depends(get_session)) -> dict:
    service = await CatalogRepository(session).create_service(1, data.model_dump())
    await session.commit()
    return {"id": service.id, "name": service.name}


@router.patch("/services/{service_id}")
async def update_service(service_id: int, data: ServiceUpdate, session: AsyncSession = Depends(get_session)) -> dict:
    service = await session.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(service, key, value)
    await session.commit()
    return {"id": service.id, "name": service.name, "is_active": service.is_active}


@router.get("/prices")
async def list_prices(session: AsyncSession = Depends(get_session)) -> list[dict]:
    prices = await CatalogRepository(session).list_prices()
    return [{"id": item.id, "service_id": item.service_id, "price_from": str(item.price_from), "price_to": str(item.price_to), "currency": item.currency, "comment": item.comment} for item in prices]


@router.post("/prices")
async def create_price(data: PriceIn, session: AsyncSession = Depends(get_session)) -> dict:
    price = Price(**data.model_dump())
    session.add(price)
    await session.commit()
    await session.refresh(price)
    return {"id": price.id}


@router.get("/leads")
async def list_leads(session: AsyncSession = Depends(get_session)) -> list[dict]:
    leads = await CRMRepository(session).list_leads()
    return [{"id": lead.id, "interest": lead.interest, "status": lead.status, "priority": lead.priority, "source_channel": lead.source_channel} for lead in leads]


@router.get("/contacts")
async def list_contacts(session: AsyncSession = Depends(get_session)) -> list[dict]:
    contacts = await CRMRepository(session).list_contacts()
    return [{"id": item.id, "full_name": item.full_name, "phone": item.phone, "created_at": item.created_at} for item in contacts]


@router.get("/conversations/{conversation_id}/messages")
async def list_conversation_messages(conversation_id: int, session: AsyncSession = Depends(get_session)) -> list[dict]:
    messages = (await session.execute(select(Message).where(Message.conversation_id == conversation_id).order_by(Message.id))).scalars().all()
    return [{"id": item.id, "sender_type": item.sender_type, "text": item.text, "created_at": item.created_at} for item in messages]


@router.get("/animal-types")
async def list_animal_types(session: AsyncSession = Depends(get_session)) -> list[dict]:
    items = (await session.execute(select(AnimalType).where(AnimalType.business_id == 1).order_by(AnimalType.name))).scalars().all()
    return [{"id": item.id, "name": item.name, "is_supported": item.is_supported, "comment": item.comment} for item in items]


@router.patch("/animal-types/{animal_type_id}")
async def update_animal_type(animal_type_id: int, data: AnimalTypeUpdate, session: AsyncSession = Depends(get_session)) -> dict:
    item = await session.get(AnimalType, animal_type_id)
    if not item:
        raise HTTPException(status_code=404, detail="Animal type not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    await session.commit()
    return {"id": item.id, "name": item.name, "is_supported": item.is_supported}


@router.get("/leads/{lead_id}")
async def get_lead(lead_id: int, session: AsyncSession = Depends(get_session)) -> dict:
    from app.db.models import Lead

    lead = await session.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"id": lead.id, "interest": lead.interest, "status": lead.status, "priority": lead.priority, "source_channel": lead.source_channel}


@router.patch("/leads/{lead_id}/status")
async def update_lead_status(lead_id: int, data: LeadStatusIn, session: AsyncSession = Depends(get_session)) -> dict:
    lead = await CRMRepository(session).set_lead_status(lead_id, data.status)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    await session.commit()
    return {"id": lead.id, "status": lead.status}


@router.get("/reports/daily")
async def daily_report(session: AsyncSession = Depends(get_session)) -> dict:
    return (await ReportGenerator(session).generate(1, "daily")).model_dump(mode="json")


@router.get("/reports/weekly")
async def weekly_report(session: AsyncSession = Depends(get_session)) -> dict:
    return (await ReportGenerator(session).generate(1, "weekly")).model_dump(mode="json")


@router.get("/reports/monthly")
async def monthly_report(session: AsyncSession = Depends(get_session)) -> dict:
    return (await ReportGenerator(session).generate(1, "monthly")).model_dump(mode="json")


@router.get("/channels")
async def list_channels(session: AsyncSession = Depends(get_session)) -> list[dict]:
    channels = (await session.execute(select(Channel).order_by(Channel.channel_type))).scalars().all()
    return [
        {
            "id": channel.id,
            "channel_type": channel.channel_type,
            "name": channel.name,
            "external_id": channel.external_id,
            "has_token_ref": bool(channel.token_ref),
            "is_active": channel.is_active,
        }
        for channel in channels
    ]


@router.patch("/channels/token")
async def update_channel_token(data: ChannelTokenIn, session: AsyncSession = Depends(get_session)) -> dict:
    result = await session.execute(select(Channel).where(Channel.business_id == 1, Channel.channel_type == data.channel_type))
    channel = result.scalars().first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    if data.token:
        try:
            channel.token_ref = encrypt_token(data.token)
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    elif data.token_ref:
        channel.token_ref = data.token_ref
    else:
        raise HTTPException(status_code=400, detail="Either token or token_ref is required")
    await session.commit()
    return {"id": channel.id, "channel_type": channel.channel_type, "has_token_ref": True}
