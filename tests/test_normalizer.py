from app.channels.normalizer import normalize_stub_webhook, normalize_telegram_update


def test_telegram_normalizer():
    message = normalize_telegram_update(
        {
            "message": {
                "date": 1,
                "text": "Здравствуйте",
                "from": {"id": 10, "first_name": "Анна", "username": "anna"},
                "chat": {"id": 20},
            }
        }
    )
    assert message.channel == "telegram"
    assert message.external_user_id == "10"
    assert message.external_chat_id == "20"
    assert message.display_name == "Анна"


def test_stub_normalizer():
    message = normalize_stub_webhook("vk", {"user_id": "u1", "chat_id": "c1", "text": "лечите кроликов?"})
    assert message.channel == "vk"
    assert message.text == "лечите кроликов?"

