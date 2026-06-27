from pydantic import ValidationError

from app.dialogs.schemas import AgentResult, Intent
from app.dialogs.state_machine import missing_minimal_fields
from app.llm.client import LLMClient
from app.llm.prompts import SYSTEM_PROMPT
from app.llm.safety import detect_emergency
from app.llm.tools import extract_animal_type, extract_phone
from app.core.logging import get_logger


logger = get_logger(__name__)


def classify_intent(text: str) -> Intent:
    lowered = text.lower()
    if detect_emergency(text):
        return Intent.emergency
    if any(word in lowered for word in ["цена", "сколько стоит", "прайс", "стоимость"]):
        return Intent.price_question
    if any(word in lowered for word in ["запис", "прием", "приём", "приехать"]):
        return Intent.appointment_request
    if any(word in lowered for word in ["адрес", "где вы", "как найти"]):
        return Intent.address_question
    if any(word in lowered for word in ["график", "работаете", "часы", "открыты"]):
        return Intent.working_hours_question
    if any(word in lowered for word in ["телефон", "номер", "позвонить"]):
        return Intent.phone_question
    if any(word in lowered for word in ["магазин", "корм", "ветмагазин"]):
        return Intent.store_question
    if any(word in lowered for word in ["жалоба", "плохо ответили", "недоволен"]):
        return Intent.complaint
    if any(word in lowered for word in ["лечите", "делаете", "есть ли", "можно", "принимаете", "стерилиз", "кастр", "привив", "узи", "рентген"]):
        return Intent.service_question
    if any(word in lowered for word in ["болит", "рвота", "вял", "не ест", "понос", "хромает"]):
        return Intent.animal_problem
    return Intent.unknown


class LLMAgent:
    def __init__(self, client: LLMClient | None = None) -> None:
        self.client = client or LLMClient()

    async def answer(self, *, text: str, context: dict) -> AgentResult:
        llm_result = await self.client.complete_json(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Верни строго JSON без markdown. Схема: "
                        '{"intent":"...", "answer_to_client":"...", "need_handoff":false, '
                        '"handoff_reason":null, "urgency":"low|normal|high|emergency", '
                        '"service_found":false, "missing_fields":[], "collected_data":{}, '
                        '"next_action":"ask_missing_field|create_lead|answer_only|handoff_to_doctor|emergency_warning", '
                        '"database_updates":{"contact":{},"animal":{},"intake_form":{},"lead":{},"handoff_task":{}}, '
                        '"doctor_notification":{"summary":null,"key_facts":[],"risk_flags":[],"recommended_action":null}}\n'
                        f"Контекст: {context}\nСообщение клиента: {text}"
                    ),
                },
            ]
        )
        if llm_result:
            try:
                return AgentResult.model_validate(llm_result)
            except ValidationError as exc:
                logger.warning("llm_result_schema_invalid_using_fallback", error=str(exc), keys=list(llm_result.keys()))
        return self._fallback_answer(text=text, context=context)

    def _fallback_answer(self, *, text: str, context: dict) -> AgentResult:
        intent = classify_intent(text)
        phone = extract_phone(text)
        animal_type = extract_animal_type(text)
        collected_data = {
            "client_name": context.get("display_name"),
            "phone": phone or context.get("contact_phone"),
            "animal_type": animal_type,
            "complaint": text if intent in {Intent.animal_problem, Intent.emergency, Intent.appointment_request} else None,
        }
        database_updates = {
            "contact": {
                "full_name": context.get("display_name"),
                "phone": phone or context.get("contact_phone"),
            },
            "animal": {
                "animal_type": animal_type,
            },
            "intake_form": collected_data,
            "lead": {},
            "handoff_task": {},
        }
        service = context.get("service")
        service_found = bool(service)

        if intent == Intent.emergency:
            database_updates["lead"] = {"interest": text, "priority": "emergency"}
            database_updates["handoff_task"] = {"reason": "Срочные симптомы в сообщении клиента", "priority": "emergency"}
            return AgentResult(
                intent=intent,
                answer_to_client=(
                    "Похоже, ситуация может быть срочной. Я AI-помощник и не могу заменить врача. "
                    f"Пожалуйста, срочно позвоните доктору по номеру {context.get('business_phone') or '+899999999'}. "
                    "Если он не отвечает, обратитесь в ближайшую круглосуточную ветеринарную клинику. "
                    "Я также передам ваше сообщение врачу."
                ),
                need_handoff=True,
                handoff_reason="Срочные симптомы в сообщении клиента",
                urgency="emergency",
                service_found=service_found,
                collected_data=collected_data,
                database_updates=database_updates,
                doctor_notification={
                    "summary": "Срочное обращение клиента, нужен быстрый контакт врача.",
                    "key_facts": [text],
                    "risk_flags": ["emergency"],
                    "recommended_action": "Позвонить клиенту как можно быстрее.",
                },
                next_action="emergency_warning",
            )

        if intent in {Intent.address_question, Intent.working_hours_question, Intent.phone_question}:
            if intent == Intent.address_question:
                answer = f"Здравствуйте! Я AI-помощник нашего доктора. Адрес клиники: {context.get('business_address') or 'уточняется'}."
            elif intent == Intent.working_hours_question:
                answer = "Здравствуйте! Я AI-помощник нашего доктора. График работы лучше уточнить у врача, я передам ваш вопрос."
            else:
                answer = f"Здравствуйте! Я AI-помощник нашего доктора. Телефон для связи: {context.get('business_phone') or '+899999999'}."
            return AgentResult(intent=intent, answer_to_client=answer, next_action="answer_only")

        if intent == Intent.store_question or (service and service.get("name") == "ветмагазин"):
            return AgentResult(
                intent=Intent.store_question,
                answer_to_client=(
                    "Здравствуйте! Я AI-помощник нашего доктора. В базе указано, что при клинике есть ветмагазин. "
                    "Напишите, пожалуйста, что именно нужно для питомца, и оставьте телефон — я передам врачу или семье клиники."
                ),
                service_found=True,
                missing_fields=["phone"] if not phone else [],
                collected_data=collected_data,
                database_updates=database_updates,
                next_action="ask_missing_field",
            )

        if service_found:
            missing = missing_minimal_fields(collected_data)
            database_updates["lead"] = {"interest": service["name"], "priority": "normal"}
            details_request = (
                "Напишите, пожалуйста, кто питомец, ваш телефон и коротко цель обращения. "
                "Например: кот, нужна кастрация, телефон ..."
            )
            return AgentResult(
                intent=intent,
                answer_to_client=(
                    f"Да, такая услуга есть: {service['name']}. "
                    f"{details_request} Я передам это доктору, чтобы он быстрее сориентировался."
                ),
                service_found=True,
                missing_fields=missing,
                collected_data=collected_data,
                database_updates=database_updates,
                doctor_notification={
                    "summary": f"Клиент интересуется услугой: {service['name']}.",
                    "key_facts": [fact for fact in [animal_type, text] if fact],
                    "risk_flags": [],
                    "recommended_action": "Связаться после сбора минимальных данных.",
                },
                next_action="create_lead" if not missing else "ask_missing_field",
            )

        if intent in {Intent.service_question, Intent.price_question}:
            return AgentResult(
                intent=intent,
                answer_to_client=(
                    "Здравствуйте! С вами общается AI-помощник нашего доктора. "
                    "К сожалению, по информации в базе, такую услугу мы сейчас не предоставляем или ее нужно уточнить у врача. "
                    "Можете оставить номер телефона — если доктор сможет подсказать безопасный следующий шаг, он свяжется с вами позже."
                ),
                service_found=False,
                need_handoff=True,
                handoff_reason="Клиент спрашивает об услуге, которой нет в базе или она требует уточнения",
                missing_fields=["phone"] if not phone else [],
                collected_data=collected_data,
                database_updates={
                    **database_updates,
                    "lead": {"interest": text, "priority": "high"},
                    "handoff_task": {"reason": "Услуга не найдена или требует уточнения", "priority": "high"},
                },
                doctor_notification={
                    "summary": "Клиент спрашивает об услуге, которой нет в базе или нужно уточнение.",
                    "key_facts": [text],
                    "risk_flags": ["service_not_found"],
                    "recommended_action": "Проверить, можно ли помочь клиенту или предложить безопасную альтернативу.",
                },
                next_action="handoff_to_doctor",
            )

        return AgentResult(
            intent=intent,
            answer_to_client=(
                "Здравствуйте! Я AI-помощник нашего доктора. Я могу подсказать по услугам клиники, "
                "ветмагазину, записи и передать заявку врачу. Напишите, пожалуйста, что нужно питомцу."
            ),
            collected_data=collected_data,
            database_updates=database_updates,
            next_action="answer_only",
        )
