import re


PHONE_RE = re.compile(r"(\+?\d[\d\s\-()]{8,}\d)")
ANIMAL_WORDS = ["кошка", "кот", "собака", "пес", "пёс", "кролик", "птица", "попугай", "грызун", "хомяк", "крыса", "рептилия"]


def extract_phone(text: str) -> str | None:
    match = PHONE_RE.search(text)
    return re.sub(r"\s+", " ", match.group(1)).strip() if match else None


def extract_animal_type(text: str) -> str | None:
    lowered = text.lower()
    for animal in ANIMAL_WORDS:
        if animal in lowered:
            if animal in {"кот", "кошка"}:
                return "кошка"
            if animal in {"пес", "пёс", "собака"}:
                return "собака"
            if animal in {"попугай", "птица"}:
                return "птица"
            return animal
    return None

