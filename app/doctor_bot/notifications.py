from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import Contact, IntakeForm, Lead
from app.doctor_bot.keyboards import lead_keyboard
from app.llm.schemas import DoctorNotificationDraft


logger = get_logger(__name__)


def _format_doctor_notification(draft: DoctorNotificationDraft | None) -> str:
    if not draft:
        return ""
    parts: list[str] = []
    if draft.summary:
        parts.append(f"AI-сводка:\n{draft.summary}")
    if draft.key_facts:
        parts.append("Ключевые факты:\n" + "\n".join(f"- {fact}" for fact in draft.key_facts[:8]))
    if draft.risk_flags:
        parts.append("Риски:\n" + "\n".join(f"- {flag}" for flag in draft.risk_flags[:6]))
    if draft.recommended_action:
        parts.append(f"Рекомендованное действие:\n{draft.recommended_action}")
    return "\n\n".join(parts)


async def format_lead_message(
    session: AsyncSession,
    lead: Lead,
    ai_answer: str | None = None,
    doctor_notification: DoctorNotificationDraft | None = None,
) -> str:
    contact = await session.get(Contact, lead.contact_id)
    form = await session.get(IntakeForm, lead.intake_form_id) if lead.intake_form_id else None
    client = (form.client_name if form else None) or (contact.full_name if contact else None) or "не указано"
    phone = (form.phone if form else None) or (contact.phone if contact else None) or "не указан"
    animal = form.animal_type if form else "не указано"
    complaint = form.complaint if form else lead.interest

    ai_doctor_block = _format_doctor_notification(doctor_notification)
    if ai_doctor_block:
        ai_doctor_block = f"\n\n{ai_doctor_block}"

    return (
        f"Новая заявка #{lead.id}\n\n"
        f"Канал: {lead.source_channel}\n"
        f"Клиент: {client}\n"
        f"Телефон: {phone}\n"
        f"Животное: {animal or 'не указано'}\n"
        f"Кличка: {(form.animal_name if form else None) or 'не указано'}\n"
        f"Порода: {(form.breed if form else None) or 'не указано'}\n"
        f"Возраст: {(form.age if form else None) or 'не указано'}\n"
        f"Пол: {(form.sex if form else None) or 'не указано'}\n"
        f"\nЖалоба:\n{complaint or 'не указано'}\n\n"
        f"Срочность: {lead.priority}\n"
        f"Статус: {lead.status}\n\n"
        f"Ответ AI:\n{ai_answer or 'не сохранен'}"
        f"{ai_doctor_block}"
    )


async def notify_doctor_about_lead(
    session: AsyncSession,
    lead: Lead,
    ai_answer: str,
    doctor_notification: DoctorNotificationDraft | None = None,
) -> None:
    settings = get_settings()
    if not settings.telegram_doctor_bot_token or not settings.doctor_telegram_user_id:
        logger.info("doctor_bot_notification_stub", lead_id=lead.id)
        return
    text = await format_lead_message(session, lead, ai_answer, doctor_notification)
    bot = Bot(settings.telegram_doctor_bot_token)
    try:
        await bot.send_message(settings.doctor_telegram_user_id, text, reply_markup=lead_keyboard(lead.id))
    finally:
        await bot.session.close()


async def lead_history_text(session: AsyncSession, lead_id: int) -> str:
    from app.db.models import Conversation, Message

    lead = await session.get(Lead, lead_id)
    if not lead:
        return "Заявка не найдена."
    conversation = await session.get(Conversation, lead.conversation_id)
    if not conversation:
        return "Диалог не найден."
    result = await session.execute(
        select(Message).where(Message.conversation_id == conversation.id).order_by(Message.id.desc()).limit(10)
    )
    messages = list(reversed(result.scalars().all()))
    lines = [f"История по заявке #{lead_id}:"]
    for message in messages:
        lines.append(f"{message.sender_type}: {message.text}")
    return "\n".join(lines)


async def lead_client_card_text(session: AsyncSession, lead_id: int) -> str:
    from sqlalchemy import func
    from app.db.models import Animal, ContactChannelAccount, Message

    lead = await session.get(Lead, lead_id)
    if not lead:
        return "Заявка не найдена."
    contact = await session.get(Contact, lead.contact_id)
    form = await session.get(IntakeForm, lead.intake_form_id) if lead.intake_form_id else None
    accounts = (await session.execute(select(ContactChannelAccount).where(ContactChannelAccount.contact_id == lead.contact_id))).scalars().all()
    animals = (await session.execute(select(Animal).where(Animal.contact_id == lead.contact_id))).scalars().all()
    messages_count = (
        await session.execute(
            select(func.count(Message.id)).where(Message.conversation_id == lead.conversation_id)
        )
    ).scalar() or 0
    channels = ", ".join(f"{account.display_name or account.username or account.external_user_id} ({account.external_chat_id})" for account in accounts) or "нет данных"
    animals_text = "\n".join(
        f"- {animal.name or 'без клички'}: {animal.animal_type or 'вид не указан'}, {animal.age or 'возраст не указан'}, {animal.sex or 'пол не указан'}"
        for animal in animals
    ) or "нет данных"
    return (
        f"Карточка клиента по заявке #{lead.id}\n\n"
        f"Имя: {(contact.full_name if contact else None) or (form.client_name if form else None) or 'не указано'}\n"
        f"Телефон: {(contact.phone if contact else None) or (form.phone if form else None) or 'не указан'}\n"
        f"Канал заявки: {lead.source_channel}\n"
        f"Аккаунты: {channels}\n"
        f"Сообщений в диалоге: {messages_count}\n"
        f"Последняя заявка: #{lead.id} — {lead.status}\n\n"
        f"Животные:\n{animals_text}"
    )
