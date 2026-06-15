import asyncio

from sqlalchemy import select

from app.crm.site_leads import SiteLeadIn, create_site_lead
from app.db.models import Channel, IntakeForm, Lead
from tests.helpers import make_test_session


def test_site_lead_creation(monkeypatch):
    async def noop(*args, **kwargs):
        return None

    async def run():
        async with make_test_session() as session:
            monkeypatch.setattr("app.crm.site_leads.notify_doctor_about_lead", noop)
            result = await create_site_lead(
                session,
                SiteLeadIn(
                    client_name="Анна",
                    phone="+7 999 111-22-33",
                    animal_type="кошка",
                    animal_name="Муся",
                    complaint="Кошка плохо ест со вчера",
                    preferred_callback_time="сегодня после 18:00",
                ),
            )
            await session.commit()

            lead = await session.get(Lead, result.lead.id)
            form = await session.get(IntakeForm, result.intake_form.id)
            channel = (await session.execute(select(Channel).where(Channel.channel_type == "site"))).scalars().first()

            assert lead is not None
            assert lead.source_channel == "site"
            assert lead.priority == "high"
            assert form is not None
            assert form.status == "ready"
            assert form.animal_type == "кошка"
            assert channel is not None

    asyncio.run(run())
