from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.db.repositories.analytics import AnalyticsRepository
from app.db.repositories.crm import CRMRepository
from app.db.session import SessionLocal
from app.doctor_bot.keyboards import reports_keyboard
from app.doctor_bot.notifications import lead_client_card_text, lead_history_text
from app.reports.generator import ReportGenerator, format_report


router = Router()


@router.message(Command("start", "help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Команды врача:\n"
        "/today — отчет за сегодня\n"
        "/week — отчет за неделю\n"
        "/month — отчет за месяц\n"
        "/leads — последние заявки\n"
        "/clients — последние клиенты\n"
        "/stuck — зависшие заявки\n"
        "/help — помощь",
        reply_markup=reports_keyboard(),
    )


async def _send_report(message: Message, report_type: str) -> None:
    async with SessionLocal() as session:
        report = await ReportGenerator(session).generate(1, report_type)
    await message.answer(format_report(report))


@router.message(Command("today"))
async def cmd_today(message: Message) -> None:
    await _send_report(message, "daily")


@router.message(Command("week"))
async def cmd_week(message: Message) -> None:
    await _send_report(message, "weekly")


@router.message(Command("month"))
async def cmd_month(message: Message) -> None:
    await _send_report(message, "monthly")


@router.message(Command("leads"))
async def cmd_leads(message: Message) -> None:
    async with SessionLocal() as session:
        leads = await CRMRepository(session).list_leads(limit=10)
    if not leads:
        await message.answer("Заявок пока нет.")
        return
    await message.answer("\n".join(f"#{lead.id} {lead.interest or 'без темы'} — {lead.status} — {lead.priority}" for lead in leads))


@router.message(Command("clients"))
async def cmd_clients(message: Message) -> None:
    async with SessionLocal() as session:
        contacts = await CRMRepository(session).list_contacts(limit=10)
    if not contacts:
        await message.answer("Клиентов пока нет.")
        return
    await message.answer("\n".join(f"#{contact.id} {contact.full_name or 'без имени'} — {contact.phone or 'телефон не указан'}" for contact in contacts))


@router.message(Command("stuck"))
async def cmd_stuck(message: Message) -> None:
    async with SessionLocal() as session:
        leads = await CRMRepository(session).stuck_leads(limit=10)
    if not leads:
        await message.answer("Зависших заявок нет.")
        return
    await message.answer("Зависшие заявки:\n\n" + "\n".join(f"#{lead.id} {lead.interest or 'без темы'} — {lead.status} — {lead.priority}" for lead in leads))


@router.callback_query(F.data.startswith("lead:"))
async def cb_lead_status(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")
    status_map = {
        "take": "in_progress",
        "callback": "callback_needed",
        "booked": "booked",
        "close": "completed",
        "lost": "lost",
    }
    if len(parts) == 3 and parts[1] in {"history", "client"}:
        lead_id = int(parts[2])
        async with SessionLocal() as session:
            text = await (lead_history_text(session, lead_id) if parts[1] == "history" else lead_client_card_text(session, lead_id))
        await callback.answer()
        await callback.message.answer(text)
        return
    if len(parts) == 3 and parts[1] in status_map:
        action = parts[1]
        lead_id = int(parts[2])
        status = status_map[action]
    else:
        _, lead_id_text, status = callback.data.split(":", 2)
        lead_id = int(lead_id_text)
    async with SessionLocal() as session:
        repo = CRMRepository(session)
        lead = await repo.set_lead_status(lead_id, status)
        if lead:
            await AnalyticsRepository(session).track(
                business_id=lead.business_id,
                event_type="lead_status_changed",
                channel=lead.source_channel,
                contact_id=lead.contact_id,
                conversation_id=lead.conversation_id,
                lead_id=lead.id,
                payload={"status": status},
            )
            await session.commit()
    await callback.answer("Статус обновлен")
    if callback.message:
        await callback.message.answer(f"Заявка #{lead_id}: {status}")


@router.callback_query(F.data.startswith("history:"))
async def cb_history(callback: CallbackQuery) -> None:
    lead_id = int(callback.data.split(":", 1)[1])
    async with SessionLocal() as session:
        text = await lead_history_text(session, lead_id)
    await callback.answer()
    await callback.message.answer(text)


@router.callback_query(F.data.startswith("report:"))
async def cb_report(callback: CallbackQuery) -> None:
    report_type = callback.data.split(":", 1)[1]
    async with SessionLocal() as session:
        report = await ReportGenerator(session).generate(1, report_type)
    await callback.answer()
    await callback.message.answer(format_report(report))
