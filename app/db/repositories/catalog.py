from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AnimalType, Business, DoctorCapability, Price, Service


class CatalogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_business(self, business_id: int = 1) -> Business | None:
        return await self.session.get(Business, business_id)

    async def search_service(self, business_id: int, text: str) -> dict | None:
        lowered = text.lower()
        result = await self.session.execute(
            select(Service).where(Service.business_id == business_id, Service.is_active.is_(True))
        )
        services = result.scalars().all()
        for service in services:
            haystack = f"{service.name} {service.category or ''} {service.description or ''}".lower()
            if any(token and token in haystack for token in lowered.replace("?", " ").split()):
                return {"id": service.id, "name": service.name, "category": service.category, "description": service.description}

        animal_result = await self.session.execute(
            select(AnimalType).where(AnimalType.business_id == business_id)
        )
        for animal in animal_result.scalars().all():
            if animal.name.lower() in lowered:
                if animal.is_supported:
                    return {"id": None, "name": f"прием: {animal.name}", "category": "animal_type", "description": animal.comment}
                return None

        capability_result = await self.session.execute(
            select(DoctorCapability).where(
                DoctorCapability.business_id == business_id,
                or_(DoctorCapability.title.ilike(f"%{text}%"), DoctorCapability.description.ilike(f"%{text}%")),
            )
        )
        capability = capability_result.scalars().first()
        if capability and capability.is_available:
            return {"id": None, "name": capability.title, "category": "capability", "description": capability.description}
        return None

    async def list_services(self, business_id: int = 1) -> list[Service]:
        result = await self.session.execute(select(Service).where(Service.business_id == business_id).order_by(Service.name))
        return list(result.scalars())

    async def create_service(self, business_id: int, data: dict) -> Service:
        service = Service(business_id=business_id, **data)
        self.session.add(service)
        await self.session.flush()
        return service

    async def list_prices(self) -> list[Price]:
        result = await self.session.execute(select(Price).order_by(Price.id))
        return list(result.scalars())

