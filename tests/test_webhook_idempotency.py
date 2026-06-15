import asyncio

from app.db.repositories.webhooks import WebhookEventRepository
from tests.helpers import make_test_session


def test_webhook_event_register_once():
    async def run():
        async with make_test_session() as session:
            repo = WebhookEventRepository(session)
            first, created_first = await repo.register_once(channel="telegram", idempotency_key="m1", raw_payload={})
            await session.commit()
            second, created_second = await repo.register_once(channel="telegram", idempotency_key="m1", raw_payload={})
            assert created_first is True
            assert created_second is False
            assert first.id == second.id

    asyncio.run(run())

