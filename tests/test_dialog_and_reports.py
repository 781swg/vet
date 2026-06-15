import asyncio

from app.channels.base import UnifiedMessage
from app.dialogs.manager import DialogManager
from app.reports.generator import ReportGenerator
from tests.helpers import make_test_session


def test_lead_creation_for_emergency(monkeypatch):
    async def noop(*args, **kwargs):
        return None

    async def run():
        async with make_test_session() as session:
            monkeypatch.setattr("app.dialogs.manager.notify_doctor_about_lead", noop)
            result = await DialogManager(session).process_message(
                UnifiedMessage(
                    channel="telegram",
                    external_user_id="100",
                    external_chat_id="200",
                    text="Кролик не ест, сильная боль, мой телефон +79999999999",
                    display_name="Анна",
                )
            )
            await session.commit()
            assert result.lead_id is not None
            assert result.need_handoff is True
            assert "срочно" in result.answer.lower()

    asyncio.run(run())


def test_report_generation(monkeypatch):
    async def noop(*args, **kwargs):
        return None

    async def run():
        async with make_test_session() as session:
            monkeypatch.setattr("app.dialogs.manager.notify_doctor_about_lead", noop)
            await DialogManager(session).process_message(
                UnifiedMessage(
                    channel="telegram",
                    external_user_id="101",
                    external_chat_id="201",
                    text="Хочу записаться на осмотр кролика, телефон +79999999999",
                    display_name="Иван",
                )
            )
            await session.commit()
            report = await ReportGenerator(session).generate(1, "daily")
            assert report.client_messages >= 1
            assert report.new_contacts >= 1
            assert report.new_leads >= 1

    asyncio.run(run())
