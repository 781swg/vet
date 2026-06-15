from collections import Counter
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Appointment, Business, Contact, HandoffTask, IntakeForm, Lead, Message
from app.reports.schemas import ReportData


class ReportGenerator:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def generate(self, business_id: int, report_type: str) -> ReportData:
        business = await self.session.get(Business, business_id)
        tz = ZoneInfo((business.timezone if business else None) or "Europe/Moscow")
        now = datetime.now(tz)
        period_start = self._period_start(report_type, now)
        return await self._build_report(business_id, report_type, period_start, now)

    def _period_start(self, report_type: str, now: datetime) -> datetime:
        if report_type == "weekly":
            return datetime.combine((now - timedelta(days=now.weekday())).date(), time.min, tzinfo=now.tzinfo)
        if report_type == "monthly":
            return datetime(now.year, now.month, 1, tzinfo=now.tzinfo)
        return datetime.combine(now.date(), time.min, tzinfo=now.tzinfo)

    async def _count(self, stmt) -> int:
        result = await self.session.execute(stmt)
        return int(result.scalar() or 0)

    async def _build_report(self, business_id: int, report_type: str, start: datetime, end: datetime) -> ReportData:
        lead_filter = and_(Lead.business_id == business_id, Lead.created_at >= start, Lead.created_at <= end)
        intake_filter = and_(IntakeForm.business_id == business_id, IntakeForm.created_at >= start, IntakeForm.created_at <= end)

        total_messages = await self._count(
            select(func.count(Message.id)).join(Lead, Lead.conversation_id == Message.conversation_id, isouter=True).where(Message.created_at >= start, Message.created_at <= end)
        )
        client_messages = await self._count(
            select(func.count(Message.id)).where(Message.sender_type == "client", Message.created_at >= start, Message.created_at <= end)
        )
        bot_messages = await self._count(
            select(func.count(Message.id)).where(Message.sender_type == "bot", Message.created_at >= start, Message.created_at <= end)
        )
        new_contacts = await self._count(
            select(func.count(Contact.id)).where(Contact.business_id == business_id, Contact.created_at >= start, Contact.created_at <= end)
        )
        new_leads = await self._count(select(func.count(Lead.id)).where(lead_filter))
        emergency_leads = await self._count(select(func.count(Lead.id)).where(lead_filter, Lead.priority == "emergency"))
        high_priority_leads = await self._count(select(func.count(Lead.id)).where(lead_filter, Lead.priority == "high"))
        appointments_created = await self._count(
            select(func.count(Appointment.id)).where(Appointment.business_id == business_id, Appointment.created_at >= start, Appointment.created_at <= end)
        )
        handoffs_created = await self._count(
            select(func.count(HandoffTask.id)).where(HandoffTask.business_id == business_id, HandoffTask.created_at >= start, HandoffTask.created_at <= end)
        )
        waiting_for_doctor_count = await self._count(select(func.count(Lead.id)).where(Lead.business_id == business_id, Lead.status == "waiting_for_doctor"))
        lost_leads_count = await self._count(select(func.count(Lead.id)).where(Lead.business_id == business_id, Lead.status == "lost"))

        leads = (await self.session.execute(select(Lead).where(lead_filter).order_by(Lead.id.desc()))).scalars().all()
        intakes = (await self.session.execute(select(IntakeForm).where(intake_filter))).scalars().all()

        latest_leads = []
        for lead in leads[:5]:
            latest_leads.append({"id": lead.id, "interest": lead.interest, "priority": lead.priority, "status": lead.status, "channel": lead.source_channel})

        return ReportData(
            report_type=report_type,
            period_start=start,
            period_end=end,
            total_messages=total_messages,
            client_messages=client_messages,
            bot_messages=bot_messages,
            new_contacts=new_contacts,
            new_leads=new_leads,
            emergency_leads=emergency_leads,
            high_priority_leads=high_priority_leads,
            leads_by_channel=dict(Counter(lead.source_channel for lead in leads)),
            leads_by_status=dict(Counter(lead.status for lead in leads)),
            top_services=Counter(lead.interest or "не указано" for lead in leads).most_common(5),
            top_animal_types=Counter(form.animal_type or "не указано" for form in intakes).most_common(5),
            appointments_created=appointments_created,
            handoffs_created=handoffs_created,
            waiting_for_doctor_count=waiting_for_doctor_count,
            lost_leads_count=lost_leads_count,
            latest_leads=latest_leads,
        )


def format_report(report: ReportData) -> str:
    title = {"daily": "Отчет за сегодня", "weekly": "Отчет за неделю", "monthly": "Отчет за месяц"}.get(report.report_type, "Отчет")
    channels = "\n".join(f"{name} — {count} заявок" for name, count in report.leads_by_channel.items()) or "нет данных"
    topics = "\n".join(f"{idx}. {name} — {count}" for idx, (name, count) in enumerate(report.top_services, 1)) or "нет данных"
    latest = "\n".join(f"#{item['id']} {item['interest']} — {item['priority']} — {item['status']}" for item in report.latest_leads) or "нет заявок"
    return (
        f"{title}\n\n"
        f"Входящие сообщения: {report.client_messages}\n"
        f"Новые клиенты: {report.new_contacts}\n"
        f"Новые заявки: {report.new_leads}\n"
        f"Срочные заявки: {report.emergency_leads}\n"
        f"Высокий приоритет: {report.high_priority_leads}\n"
        f"Записано на прием: {report.appointments_created}\n"
        f"Ожидают ответа врача: {report.waiting_for_doctor_count}\n"
        f"Потеряно: {report.lost_leads_count}\n\n"
        f"Каналы:\n{channels}\n\n"
        f"Популярные темы:\n{topics}\n\n"
        f"Последние заявки:\n{latest}"
    )

