from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.channels.base import UnifiedMessage
from app.db.repositories.analytics import AnalyticsRepository
from app.db.repositories.catalog import CatalogRepository
from app.db.repositories.crm import CRMRepository
from app.dialogs.intake import extract_intake_data, form_data, is_minimal_ready, next_intake_question
from app.dialogs.state_machine import DialogState
from app.dialogs.state_machine import missing_minimal_fields
from app.doctor_bot.notifications import notify_doctor_about_lead
from app.llm.agent import LLMAgent
from app.llm.safety import validate_medical_answer
from app.llm.sql_tools import SQLToolbox


@dataclass
class DialogProcessResult:
    answer: str
    lead_id: int | None = None
    need_handoff: bool = False


READY_STATES = {DialogState.lead_created, DialogState.waiting_for_doctor}
START_COMMANDS = {"/start", "start"}
SERVICE_REQUEST_HINTS = ("кастр", "стерилиз", "привив", "вакцин", "запис", "нужн", "хочу")
PURE_QUESTION_HINTS = ("лечите", "есть ли", "можно", "?")


def _service_request_as_complaint(text: str, service: dict | None) -> str | None:
    if not service:
        return None
    lowered = text.lower()
    if any(hint in lowered for hint in PURE_QUESTION_HINTS) and not any(hint in lowered for hint in SERVICE_REQUEST_HINTS):
        return None
    if any(hint in lowered for hint in SERVICE_REQUEST_HINTS):
        return f"Интересует услуга: {service['name']}"
    return None


class DialogManager:
    def __init__(self, session: AsyncSession, agent: LLMAgent | None = None) -> None:
        self.session = session
        self.crm = CRMRepository(session)
        self.catalog = CatalogRepository(session)
        self.analytics = AnalyticsRepository(session)
        self.agent = agent or LLMAgent()

    async def process_message(self, message: UnifiedMessage) -> DialogProcessResult:
        channel = await self.crm.get_or_create_channel(message.business_id, message.channel)
        contact, contact_created = await self.crm.get_or_create_contact(message, channel)
        conversation, conversation_created = await self.crm.get_or_create_conversation(message.business_id, contact.id, channel.id)
        active_form = await self.crm.get_active_intake(conversation.id)
        is_collecting = active_form is not None or conversation.status in {
            DialogState.collecting_intake,
            DialogState.waiting_for_phone,
            DialogState.waiting_for_animal_info,
            DialogState.waiting_for_complaint,
        }

        await self.crm.add_message(conversation.id, "client", message.text, raw_payload=message.raw_payload)
        conversation.last_message_at = message.timestamp
        await self.analytics.track(business_id=message.business_id, event_type="message_received", channel=message.channel, contact_id=contact.id, conversation_id=conversation.id)
        if contact_created:
            await self.analytics.track(business_id=message.business_id, event_type="contact_created", channel=message.channel, contact_id=contact.id)
        if conversation_created:
            await self.analytics.track(business_id=message.business_id, event_type="conversation_created", channel=message.channel, contact_id=contact.id, conversation_id=conversation.id)

        if conversation.status in READY_STATES and message.text.strip().lower() not in START_COMMANDS:
            lead = await self.crm.find_latest_lead_for_conversation(conversation.id)
            if lead:
                answer = (
                    f"Спасибо, я добавил это к заявке #{lead.id}. "
                    "Доктор увидит уточнение в истории диалога. Если есть фото, видео или удобное время для звонка, "
                    "можете отправить здесь же."
                )
                await self.crm.add_message(conversation.id, "bot", answer)
                await self.analytics.track(
                    business_id=message.business_id,
                    event_type="bot_replied",
                    channel=message.channel,
                    contact_id=contact.id,
                    conversation_id=conversation.id,
                    lead_id=lead.id,
                )
                await notify_doctor_about_lead(
                    self.session,
                    lead,
                    f"Клиент добавил уточнение: {message.text}",
                    None,
                )
                await self.analytics.track(
                    business_id=message.business_id,
                    event_type="doctor_notified",
                    channel=message.channel,
                    contact_id=contact.id,
                    conversation_id=conversation.id,
                    lead_id=lead.id,
                )
                return DialogProcessResult(answer=answer, lead_id=lead.id, need_handoff=False)

        tool_context = await SQLToolbox(self.session).build_context(business_id=message.business_id, query=message.text)
        business_data = tool_context["business"]
        service = tool_context["service"]
        context = {
            "display_name": contact.full_name or message.display_name,
            "contact_phone": contact.phone,
            "service": service,
            "business_phone": business_data.get("phone"),
            "business_address": business_data.get("address"),
            "knowledge_chunks": tool_context["knowledge_chunks"],
            "doctor_capabilities": tool_context["doctor_capabilities"],
            "business_rules": tool_context["business_rules"],
        }
        result = await self.agent.answer(text=message.text, context={**context, "dialog_state": conversation.status, "active_intake": form_data(active_form) if active_form else None})
        if service and not result.service_found:
            result.service_found = True
        if result.urgency == "emergency" or result.intent.value == "emergency":
            result.need_handoff = True
            result.urgency = "emergency"
            answer = (
                "Похоже, ситуация может быть срочной. Я AI-помощник и не могу заменить врача. "
                f"Пожалуйста, срочно позвоните доктору по номеру {business_data.get('phone') or '+899999999'}. "
                "Если он не отвечает, обратитесь в ближайшую круглосуточную ветеринарную клинику. "
                "Я также передам ваше сообщение врачу."
            )
        else:
            answer = validate_medical_answer(result.answer_to_client)
        conversation.current_intent = result.intent.value

        await self.analytics.track(
            business_id=message.business_id,
            event_type="intent_detected",
            channel=message.channel,
            contact_id=contact.id,
            conversation_id=conversation.id,
            payload={"intent": result.intent.value},
        )
        await self.analytics.track(
            business_id=message.business_id,
            event_type="service_found" if result.service_found else "service_not_found",
            channel=message.channel,
            contact_id=contact.id,
            conversation_id=conversation.id,
            payload={"service": service},
        )

        lead = None
        extracted_data = extract_intake_data(
            message.text,
            display_name=contact.full_name or message.display_name,
            ongoing=is_collecting or result.service_found or result.next_action in {"ask_missing_field", "create_lead"},
        )
        # LLM is responsible for semantic extraction and deciding which business
        # entity each field belongs to. Deterministic extractors only fill or
        # correct simple fields such as phone/animal keywords before SQL writes.
        llm_database_data = result.database_intake_data()
        collected_data = {**extracted_data, **result.collected_data, **llm_database_data}
        if extracted_data.get("phone"):
            collected_data["phone"] = extracted_data["phone"]
        if extracted_data.get("animal_type") and not collected_data.get("animal_type"):
            collected_data["animal_type"] = extracted_data["animal_type"]
        service_complaint = _service_request_as_complaint(message.text, service)
        if service_complaint and not collected_data.get("complaint"):
            collected_data["complaint"] = service_complaint
        if result.intent.value in {"appointment_request", "animal_problem", "emergency"} and not collected_data.get("complaint"):
            collected_data["complaint"] = message.text
        should_collect_intake = bool(collected_data) and (
            is_collecting
            or result.service_found
            or result.next_action in {"ask_missing_field", "create_lead", "handoff_to_doctor", "emergency_warning"}
        )
        lead_priority = result.database_updates.lead.priority or (
            "emergency" if result.urgency == "emergency" else "high" if result.urgency == "high" else "normal"
        )

        if should_collect_intake:
            intake_was_active = active_form is not None
            form = await self.crm.create_or_update_intake(
                business_id=message.business_id,
                contact_id=contact.id,
                conversation_id=conversation.id,
                source_channel=message.channel,
                data=collected_data,
                urgency=result.urgency,
            )
            await self.crm.update_contact_from_intake(contact.id, form)
            await self.crm.ensure_animal_from_intake(form)
            if not intake_was_active:
                await self.analytics.track(business_id=message.business_id, event_type="intake_started", channel=message.channel, contact_id=contact.id, conversation_id=conversation.id)
            await self.analytics.track(business_id=message.business_id, event_type="intake_updated", channel=message.channel, contact_id=contact.id, conversation_id=conversation.id)
            form_missing = missing_minimal_fields(form_data(form))
            should_create_lead = (
                result.next_action in {"create_lead", "handoff_to_doctor", "emergency_warning"}
                or is_minimal_ready(form)
            )
            if should_create_lead:
                lead = await self.crm.find_lead_for_intake(form.id)
                if not lead:
                    lead = await self.crm.create_lead(
                        business_id=message.business_id,
                        contact_id=contact.id,
                        conversation_id=conversation.id,
                        intake_form_id=form.id,
                        source_channel=message.channel,
                        interest=result.database_updates.lead.interest or (service["name"] if service else message.text),
                        priority=lead_priority,
                    )
                    await self.analytics.track(business_id=message.business_id, event_type="lead_created", channel=message.channel, contact_id=contact.id, conversation_id=conversation.id, lead_id=lead.id)
                form.status = "ready"
                conversation.status = DialogState.waiting_for_doctor
                if result.urgency != "emergency":
                    answer = (
                        f"Спасибо, я передал заявку доктору. Номер заявки: #{lead.id}. "
                        "Он посмотрит данные и свяжется с вами, как только освободится. "
                        "Если есть фото, видео или удобное время для звонка, можете отправить здесь же."
                    )
            elif form_missing:
                if "phone" in form_missing:
                    conversation.status = DialogState.waiting_for_phone
                elif "animal_type" in form_missing:
                    conversation.status = DialogState.waiting_for_animal_info
                elif "complaint" in form_missing:
                    conversation.status = DialogState.waiting_for_complaint
                else:
                    conversation.status = DialogState.collecting_intake
                if is_collecting:
                    answer = next_intake_question(form_missing)
                else:
                    conversation.status = DialogState.collecting_intake

        if result.need_handoff:
            if not lead:
                lead = await self.crm.create_lead(
                    business_id=message.business_id,
                    contact_id=contact.id,
                    conversation_id=conversation.id,
                    intake_form_id=None,
                    source_channel=message.channel,
                    interest=result.database_updates.lead.interest or message.text,
                    priority=result.database_updates.lead.priority or ("emergency" if result.urgency == "emergency" else "high"),
                )
                await self.analytics.track(business_id=message.business_id, event_type="lead_created", channel=message.channel, contact_id=contact.id, conversation_id=conversation.id, lead_id=lead.id)
            await self.crm.create_handoff(
                business_id=message.business_id,
                conversation_id=conversation.id,
                lead_id=lead.id,
                reason=result.database_updates.handoff_task.reason or result.handoff_reason or "Нужен врач",
                priority=result.database_updates.handoff_task.priority or lead.priority,
            )
            await self.analytics.track(business_id=message.business_id, event_type="handoff_created", channel=message.channel, contact_id=contact.id, conversation_id=conversation.id, lead_id=lead.id)
            if result.urgency == "emergency":
                await self.analytics.track(business_id=message.business_id, event_type="emergency_detected", channel=message.channel, contact_id=contact.id, conversation_id=conversation.id, lead_id=lead.id)
            conversation.status = DialogState.waiting_for_doctor

        if not should_collect_intake and not result.need_handoff:
            conversation.status = DialogState.answering_question

        await self.crm.add_message(conversation.id, "bot", answer, llm_context=result.model_dump(mode="json"))
        await self.analytics.track(business_id=message.business_id, event_type="bot_replied", channel=message.channel, contact_id=contact.id, conversation_id=conversation.id, lead_id=lead.id if lead else None)

        if lead:
            await notify_doctor_about_lead(self.session, lead, answer, result.doctor_notification)
            await self.analytics.track(business_id=message.business_id, event_type="doctor_notified", channel=message.channel, contact_id=contact.id, conversation_id=conversation.id, lead_id=lead.id)

        return DialogProcessResult(answer=answer, lead_id=lead.id if lead else None, need_handoff=result.need_handoff)
