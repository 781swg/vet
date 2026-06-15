from app.dialogs.schemas import Intent
from app.llm.agent import classify_intent
from app.llm.safety import detect_emergency, validate_medical_answer


def test_emergency_detection():
    assert detect_emergency("У собаки судороги и она тяжело дышит")
    assert classify_intent("Кот не может мочиться") == Intent.emergency


def test_intent_detection_mock():
    assert classify_intent("Вы лечите кроликов?") == Intent.service_question
    assert classify_intent("Сколько стоит вакцинация?") == Intent.price_question
    assert classify_intent("Можно записаться на прием?") == Intent.appointment_request


def test_safety_validator_blocks_dosage_like_answer():
    answer = validate_medical_answer("Дайте 2 мл препарата, это точно поможет")
    assert "не могу ставить диагнозы" in answer

