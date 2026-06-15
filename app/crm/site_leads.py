from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha1

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import Contact, ContactChannelAccount, Conversation, HandoffTask, IntakeForm, Lead
from app.db.repositories.analytics import AnalyticsRepository
from app.db.repositories.crm import CRMRepository
from app.doctor_bot.notifications import notify_doctor_about_lead


logger = get_logger(__name__)

EMERGENCY_HINTS = (
    "кровотеч",
    "судорог",
    "потерял сознание",
    "потеряла сознание",
    "не дыш",
    "задыха",
    "отрав",
    "травм",
    "не может моч",
    "мочиться не может",
    "многократная рвота",
    "инородн",
    "сильная боль",
    "умира",
    "род",
)

HIGH_PRIORITY_HINTS = (
    "ноч",
    "сроч",
    "плохо",
    "не ест",
    "вял",
    "рв",
    "понос",
    "боль",
    "кров",
)


class SiteLeadIn(BaseModel):
    client_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=64)
    animal_type: str | None = Field(default=None, max_length=128)
    animal_name: str | None = Field(default=None, max_length=255)
    breed: str | None = Field(default=None, max_length=255)
    age: str | None = Field(default=None, max_length=128)
    sex: str | None = Field(default=None, max_length=64)
    complaint: str = Field(min_length=3, max_length=4000)
    preferred_callback_time: str | None = Field(default=None, max_length=255)
    source_page: str | None = Field(default=None, max_length=512)
    consent: bool = True

    @field_validator("*", mode="before")
    @classmethod
    def empty_to_none(cls, value):
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


@dataclass(slots=True)
class SiteLeadResult:
    lead: Lead
    intake_form: IntakeForm
    notification_sent: bool


def detect_priority(text: str) -> str:
    lowered = text.lower()
    if any(hint in lowered for hint in EMERGENCY_HINTS):
        return "emergency"
    if any(hint in lowered for hint in HIGH_PRIORITY_HINTS):
        return "high"
    return "normal"


def format_site_lead_text(data: SiteLeadIn) -> str:
    lines = [
        "Заявка с сайта",
        f"Имя: {data.client_name or 'не указано'}",
        f"Телефон: {data.phone or 'не указан'}",
        f"Питомец: {data.animal_type or 'не указан'}",
        f"Кличка: {data.animal_name or 'не указана'}",
        f"Порода: {data.breed or 'не указана'}",
        f"Возраст: {data.age or 'не указан'}",
        f"Пол: {data.sex or 'не указан'}",
        f"Удобное время: {data.preferred_callback_time or 'не указано'}",
        "",
        f"Сообщение: {data.complaint}",
    ]
    return "\n".join(lines)


def site_external_user_id(data: SiteLeadIn) -> str:
    stable = data.phone or data.client_name or data.complaint
    digest = sha1(stable.encode("utf-8")).hexdigest()[:16]
    return f"site:{digest}"


async def create_site_lead(session: AsyncSession, data: SiteLeadIn, *, business_id: int = 1) -> SiteLeadResult:
    settings = get_settings()
    crm = CRMRepository(session)
    analytics = AnalyticsRepository(session)
    channel = await crm.get_or_create_channel(business_id, "site")

    contact_created = False
    contact = None
    if data.phone:
        contact = (
            await session.execute(select(Contact).where(Contact.business_id == business_id, Contact.phone == data.phone))
        ).scalars().first()
    if not contact:
        contact = Contact(business_id=business_id, full_name=data.client_name, phone=data.phone)
        session.add(contact)
        await session.flush()
        contact_created = True
    else:
        if data.client_name and not contact.full_name:
            contact.full_name = data.client_name
        if data.phone and not contact.phone:
            contact.phone = data.phone
        await session.flush()

    external_user_id = site_external_user_id(data)
    account = (
        await session.execute(
            select(ContactChannelAccount).where(
                ContactChannelAccount.channel_id == channel.id,
                ContactChannelAccount.external_user_id == external_user_id,
            )
        )
    ).scalars().first()
    if not account:
        session.add(
            ContactChannelAccount(
                contact_id=contact.id,
                channel_id=channel.id,
                external_user_id=external_user_id,
                external_chat_id=external_user_id,
                username=None,
                display_name=data.client_name,
                created_at=datetime.now(UTC),
            )
        )

    conversation = Conversation(
        business_id=business_id,
        contact_id=contact.id,
        channel_id=channel.id,
        status="waiting_for_doctor",
        current_intent="appointment_request",
        last_message_at=datetime.now(UTC),
    )
    session.add(conversation)
    await session.flush()

    raw_payload = data.model_dump(mode="json")
    await crm.add_message(conversation.id, "client", format_site_lead_text(data), raw_payload=raw_payload)
    await analytics.track(business_id=business_id, event_type="message_received", channel="site", contact_id=contact.id, conversation_id=conversation.id, payload={"source_page": data.source_page})
    if contact_created:
        await analytics.track(business_id=business_id, event_type="contact_created", channel="site", contact_id=contact.id)
    await analytics.track(business_id=business_id, event_type="conversation_created", channel="site", contact_id=contact.id, conversation_id=conversation.id)

    priority = detect_priority(data.complaint)
    form = IntakeForm(
        business_id=business_id,
        contact_id=contact.id,
        animal_id=None,
        conversation_id=conversation.id,
        client_name=data.client_name,
        phone=data.phone,
        animal_type=data.animal_type,
        animal_name=data.animal_name,
        breed=data.breed,
        age=data.age,
        sex=data.sex,
        complaint=data.complaint,
        preferred_callback_time=data.preferred_callback_time,
        source_channel="site",
        urgency=priority,
        status="ready",
    )
    session.add(form)
    await session.flush()
    await crm.ensure_animal_from_intake(form)
    await analytics.track(business_id=business_id, event_type="intake_started", channel="site", contact_id=contact.id, conversation_id=conversation.id)
    await analytics.track(business_id=business_id, event_type="intake_updated", channel="site", contact_id=contact.id, conversation_id=conversation.id)

    lead = await crm.create_lead(
        business_id=business_id,
        contact_id=contact.id,
        conversation_id=conversation.id,
        intake_form_id=form.id,
        source_channel="site",
        interest=data.complaint,
        priority=priority,
    )
    await analytics.track(business_id=business_id, event_type="lead_created", channel="site", contact_id=contact.id, conversation_id=conversation.id, lead_id=lead.id)

    if priority in {"high", "emergency"}:
        session.add(
            HandoffTask(
                business_id=business_id,
                conversation_id=conversation.id,
                lead_id=lead.id,
                reason="Заявка с сайта требует внимания врача",
                priority=priority,
                status="open",
            )
        )
        await analytics.track(business_id=business_id, event_type="handoff_created", channel="site", contact_id=contact.id, conversation_id=conversation.id, lead_id=lead.id)
        if priority == "emergency":
            await analytics.track(business_id=business_id, event_type="emergency_detected", channel="site", contact_id=contact.id, conversation_id=conversation.id, lead_id=lead.id)

    ai_answer = (
        "Заявка создана с сайта. Клиент ждет обратной связи. "
        f"Основной бот для заявок: @{settings.telegram_client_bot_username}."
    )
    await crm.add_message(conversation.id, "bot", ai_answer, llm_context={"source": "site_form", "lead_id": lead.id})
    await analytics.track(business_id=business_id, event_type="bot_replied", channel="site", contact_id=contact.id, conversation_id=conversation.id, lead_id=lead.id)

    notification_sent = False
    try:
        await notify_doctor_about_lead(session, lead, ai_answer)
        notification_sent = bool(settings.telegram_doctor_bot_token and settings.doctor_telegram_user_id)
        await analytics.track(business_id=business_id, event_type="doctor_notified", channel="site", contact_id=contact.id, conversation_id=conversation.id, lead_id=lead.id)
    except Exception as exc:
        logger.exception("site_lead_doctor_notification_failed", lead_id=lead.id, error=str(exc))

    return SiteLeadResult(lead=lead, intake_form=form, notification_sent=notification_sent)
