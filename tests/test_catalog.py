import asyncio

from app.db.repositories.catalog import CatalogRepository
from tests.helpers import make_test_session


def test_service_search():
    async def run():
        async with make_test_session() as session:
            service = await CatalogRepository(session).search_service(1, "Вы лечите кроликов?")
            assert service is not None
            assert "кролик" in service["name"]

    asyncio.run(run())
