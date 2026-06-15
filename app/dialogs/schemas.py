from enum import StrEnum

from app.llm.schemas import LLMAgentResult


class Intent(StrEnum):
    service_question = "service_question"
    price_question = "price_question"
    appointment_request = "appointment_request"
    animal_problem = "animal_problem"
    emergency = "emergency"
    store_question = "store_question"
    address_question = "address_question"
    working_hours_question = "working_hours_question"
    phone_question = "phone_question"
    doctor_question = "doctor_question"
    complaint = "complaint"
    unknown = "unknown"
    human_required = "human_required"


class AgentResult(LLMAgentResult):
    intent: Intent = Intent.unknown
