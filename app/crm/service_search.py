from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.catalog import CatalogRepository
from app.db.repositories.knowledge import KnowledgeRepository


@dataclass
class ServiceMatch:
    name: str
    category: str | None
    description: str | None
    confidence: float = 1.0


async def search_services_by_text(session: AsyncSession, business_id: int, text: str) -> list[ServiceMatch]:
    service = await CatalogRepository(session).search_service(business_id, text)
    if not service:
        return []
    return [ServiceMatch(name=service["name"], category=service.get("category"), description=service.get("description"))]


async def search_animal_type(session: AsyncSession, business_id: int, text: str) -> dict | None:
    service = await CatalogRepository(session).search_service(business_id, text)
    if service and service.get("category") == "animal_type":
        return service
    return None


async def get_capabilities_for_question(session: AsyncSession, business_id: int, text: str) -> list[dict]:
    return await KnowledgeRepository(session).capability_matches(business_id, text)

