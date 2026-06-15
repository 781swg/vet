from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.catalog import CatalogRepository
from app.db.repositories.knowledge import KnowledgeRepository


class SQLToolbox:
    """Whitelisted SQL-backed tools available to the LLM layer."""

    def __init__(self, session: AsyncSession) -> None:
        self.catalog = CatalogRepository(session)
        self.knowledge = KnowledgeRepository(session)

    async def build_context(self, *, business_id: int, query: str) -> dict:
        business = await self.catalog.get_business(business_id)
        service = await self.catalog.search_service(business_id, query)
        return {
            "business": {
                "id": business.id if business else business_id,
                "name": business.name if business else None,
                "phone": business.phone if business else None,
                "address": business.address if business else None,
                "timezone": business.timezone if business else None,
            },
            "service": service,
            "knowledge_chunks": await self.knowledge.search(business_id, query),
            "doctor_capabilities": await self.knowledge.capability_matches(business_id, query),
            "business_rules": await self.knowledge.business_rules(business_id),
        }

