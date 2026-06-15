from enum import StrEnum


class DialogState(StrEnum):
    idle = "idle"
    answering_question = "answering_question"
    collecting_intake = "collecting_intake"
    waiting_for_phone = "waiting_for_phone"
    waiting_for_animal_info = "waiting_for_animal_info"
    waiting_for_complaint = "waiting_for_complaint"
    lead_created = "lead_created"
    waiting_for_doctor = "waiting_for_doctor"
    closed = "closed"


MINIMAL_LEAD_FIELDS = {"client_name", "phone", "animal_type", "complaint"}


def missing_minimal_fields(data: dict) -> list[str]:
    return [field for field in MINIMAL_LEAD_FIELDS if not data.get(field)]

