import asyncio

from sqlalchemy import select

from app.channels.base import UnifiedMessage
from app.db.models import Animal, Contact, IntakeForm, Lead
from app.dialogs.manager import DialogManager
from app.dialogs.schemas import AgentResult, Intent
from tests.helpers import make_test_session


class FakeAgent:
    async def answer(self, text: str, context: dict) -> AgentResult:
        if "лечите кроликов" in text.lower():
            return AgentResult(
                intent=Intent.service_question,
                answer_to_client="Да, доктор принимает кроликов. Напишите кличку, возраст, жалобу и телефон.",
                urgency="normal",
                service_found=True,
                missing_fields=["phone", "animal_name", "complaint"],
                database_updates={
                    "animal": {"animal_type": "кролик"},
                    "intake_form": {"animal_type": "кролик"},
                    "lead": {"interest": "осмотр кролика", "priority": "normal"},
                    "handoff_task": {},
                    "contact": {},
                },
                next_action="ask_missing_field",
            )
        return AgentResult(
            intent=Intent.animal_problem,
            answer_to_client="Спасибо, уточню данные для врача.",
            urgency="normal",
            service_found=True,
            database_updates={
                "animal": {"name": "Пушок", "animal_type": "кролик", "age": "2 года", "sex": "самец"},
                "intake_form": {
                    "animal_name": "Пушок",
                    "animal_type": "кролик",
                    "age": "2 года",
                    "sex": "самец",
                    "complaint": "плохо ест с утра",
                },
                "lead": {"interest": "осмотр кролика", "priority": "normal"},
                "handoff_task": {},
                "contact": {},
            },
            doctor_notification={
                "summary": "Кролик Пушок, 2 года, плохо ест с утра.",
                "key_facts": ["кролик", "Пушок", "плохо ест с утра"],
                "risk_flags": [],
                "recommended_action": "Перезвонить после получения телефона.",
            },
            next_action="ask_missing_field",
        )


def test_multiturn_intake_collects_phone_and_creates_lead(monkeypatch):
    async def noop(*args, **kwargs):
        return None

    async def run():
        async with make_test_session() as session:
            monkeypatch.setattr("app.dialogs.manager.notify_doctor_about_lead", noop)
            manager = DialogManager(session, agent=FakeAgent())

            first = await manager.process_message(
                UnifiedMessage(
                    channel="telegram",
                    external_user_id="300",
                    external_chat_id="400",
                    text="Здравствуйте, вы лечите кроликов?",
                    display_name="Анна",
                )
            )
            assert first.lead_id is None

            second = await manager.process_message(
                UnifiedMessage(
                    channel="telegram",
                    external_user_id="300",
                    external_chat_id="400",
                    text="Отправляю анкету питомца",
                    display_name="Анна",
                )
            )
            assert "телефон" in second.answer.lower()
            assert second.lead_id is None

            third = await manager.process_message(
                UnifiedMessage(
                    channel="telegram",
                    external_user_id="300",
                    external_chat_id="400",
                    text="+79999999999",
                    display_name="Анна",
                )
            )
            await session.commit()

            assert third.lead_id is not None
            assert "передал заявку доктору" in third.answer.lower()

            contact = await session.scalar(select(Contact).where(Contact.phone == "+79999999999"))
            form = await session.scalar(select(IntakeForm).where(IntakeForm.phone == "+79999999999"))
            lead = await session.scalar(select(Lead).where(Lead.id == third.lead_id))
            animal = await session.scalar(select(Animal).where(Animal.contact_id == contact.id))

            assert contact is not None
            assert form is not None
            assert lead is not None
            assert animal is not None
            assert form.animal_type == "кролик"
            assert form.animal_name == "Пушок"
            assert form.complaint == "плохо ест с утра"
            assert animal.name == "Пушок"

    asyncio.run(run())


def test_service_request_becomes_ready_without_repeating_complaint(monkeypatch):
    async def noop(*args, **kwargs):
        return None

    async def run():
        async with make_test_session() as session:
            monkeypatch.setattr("app.dialogs.manager.notify_doctor_about_lead", noop)
            manager = DialogManager(session)

            first = await manager.process_message(
                UnifiedMessage(
                    channel="telegram",
                    external_user_id="301",
                    external_chat_id="401",
                    text="кастрация",
                    display_name="Алексей",
                )
            )
            assert first.lead_id is None

            second = await manager.process_message(
                UnifiedMessage(
                    channel="telegram",
                    external_user_id="301",
                    external_chat_id="401",
                    text="кот нужно кастрировать 79513888833",
                    display_name="Алексей",
                )
            )
            assert second.lead_id is not None
            assert "заявк" in second.answer.lower()
            assert "что беспокоит" not in second.answer.lower()

            third = await manager.process_message(
                UnifiedMessage(
                    channel="telegram",
                    external_user_id="301",
                    external_chat_id="401",
                    text="лучше звонить вечером",
                    display_name="Алексей",
                )
            )
            assert third.lead_id == second.lead_id
            assert "добавил" in third.answer.lower()
            assert "что беспокоит" not in third.answer.lower()

    asyncio.run(run())
