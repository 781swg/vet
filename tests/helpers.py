from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import AnimalType, Business, Channel, Service


@asynccontextmanager
async def make_test_session() -> AsyncIterator:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        business = Business(
            id=1,
            name="Ветклиника Дениса",
            phone="+899999999",
            address="Тестовый адрес",
            timezone="Europe/Moscow",
            description="Тест",
            working_hours={},
        )
        session.add(business)
        session.add(Channel(business_id=1, channel_type="telegram", name="Telegram", is_active=True))
        session.add(Service(business_id=1, name="осмотр кролика", category="прием", description="Осмотр кроликов", is_active=True, requires_doctor_confirmation=True))
        session.add(Service(business_id=1, name="вакцинация", category="профилактика", description="Прививки", is_active=True, requires_doctor_confirmation=True))
        session.add(AnimalType(business_id=1, name="кролик", is_supported=True, comment="Принимаем кроликов"))
        await session.commit()
        yield session
    await engine.dispose()
