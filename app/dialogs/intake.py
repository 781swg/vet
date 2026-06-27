import re

from app.dialogs.state_machine import missing_minimal_fields
from app.llm.tools import extract_animal_type, extract_phone


QUESTION_HINTS = ["лечите", "делаете", "есть ли", "можно", "сколько", "цена", "адрес", "график"]
COMPLAINT_HINTS = ["не ест", "вял", "рв", "понос", "бол", "кров", "хром", "чих", "каш", "плохо", "с утра", "со вчера", "жалоб"]


def extract_intake_data(text: str, *, display_name: str | None = None, ongoing: bool = False) -> dict:
    lowered = text.lower()
    data: dict = {}

    phone = extract_phone(text)
    if phone:
        data["phone"] = phone

    animal_type = extract_animal_type(text)
    if animal_type:
        data["animal_type"] = animal_type

    name_match = re.search(r"(?:зовут|кличка|имя)\s+([А-Яа-яA-Za-zёЁ-]{2,32})", text, re.IGNORECASE)
    if name_match:
        data["animal_name"] = name_match.group(1).strip(" ,.")
    elif ongoing and "," in text and not any(hint in lowered for hint in QUESTION_HINTS):
        first_part = text.split(",", 1)[0].strip()
        if 1 <= len(first_part.split()) <= 3 and first_part.lower() not in {"здравствуйте", "добрый день", "привет"}:
            data["animal_name"] = first_part.split()[0].strip(" ,.")

    age_match = re.search(r"(\d{1,2}\s*(?:год(?:а|ик|ов)?|лет|месяц(?:а|ев)?|мес\.?))", text, re.IGNORECASE)
    if age_match:
        data["age"] = age_match.group(1).strip()

    if any(word in lowered for word in ["мальчик", "самец", "кот", "кобель"]):
        data["sex"] = "самец"
    elif any(word in lowered for word in ["девочка", "самка", "кошка", "сука"]):
        data["sex"] = "самка"

    if any(hint in lowered for hint in COMPLAINT_HINTS):
        complaint_parts = [
            part.strip()
            for part in text.split(",")
            if any(hint in part.lower() for hint in COMPLAINT_HINTS)
        ]
        data["complaint"] = complaint_parts[-1] if complaint_parts else text.strip()
    elif ongoing and not phone and not any(hint in lowered for hint in QUESTION_HINTS):
        data["complaint"] = text.strip()

    if display_name:
        data["client_name"] = display_name

    return {key: value for key, value in data.items() if value}


def form_data(form) -> dict:
    return {
        "client_name": form.client_name,
        "phone": form.phone,
        "animal_type": form.animal_type,
        "animal_name": form.animal_name,
        "breed": form.breed,
        "age": form.age,
        "sex": form.sex,
        "complaint": form.complaint,
    }


def next_intake_question(missing: list[str]) -> str:
    if "phone" in missing:
        return "Спасибо. Оставьте, пожалуйста, номер телефона, чтобы доктор мог связаться с вами."
    if "animal_type" in missing:
        return "Кто у вас питомец: кошка, собака, кролик, морская свинка или другое животное?"
    if "complaint" in missing:
        return "Коротко напишите, что нужно питомцу или что его беспокоит. Например: кастрация кота, прививка, не ест со вчера."
    if "client_name" in missing:
        return "Как к вам можно обращаться?"
    return "Спасибо, я уточню детали и передам врачу."


def is_minimal_ready(form) -> bool:
    return not missing_minimal_fields(form_data(form))
