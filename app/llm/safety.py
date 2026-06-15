import re


EMERGENCY_PATTERNS = [
    r"кровотеч",
    r"судорог",
    r"потер[яял].*созн",
    r"не дыш",
    r"трудно дыш",
    r"задыха",
    r"отрав",
    r"травм",
    r"сбил[аи]?",
    r"не может моч",
    r"не писает",
    r"многократн.*рв",
    r"рв[её]т.*много",
    r"резко.*хуже",
    r"роды",
    r"инородн",
    r"сильн.*бол",
]

FORBIDDEN_MEDICAL_PATTERNS = [
    r"\bдиагноз\b",
    r"\bдозировк",
    r"\bмг\b",
    r"\bмл\b",
    r"назнач(аю|ение|ить)",
    r"это точно",
    r"гарант",
]


def detect_emergency(text: str) -> bool:
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in EMERGENCY_PATTERNS)


def validate_medical_answer(answer: str) -> str:
    lowered = answer.lower()
    if any(re.search(pattern, lowered) for pattern in FORBIDDEN_MEDICAL_PATTERNS):
        return (
            "Я AI-помощник и не могу ставить диагнозы, назначать лечение или дозировки. "
            "Я передам ваше сообщение врачу, а если состояние ухудшается — пожалуйста, срочно звоните в клинику."
        )
    return answer

