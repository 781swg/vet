from app.channels.max_adapter import MaxAdapter
from app.channels.whatsapp_adapter import WhatsAppAdapter


def test_whatsapp_adapter_parses_meta_payload():
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [{"wa_id": "79999999999", "profile": {"name": "Анна"}}],
                            "messages": [
                                {
                                    "from": "79999999999",
                                    "id": "wamid.1",
                                    "timestamp": "1710000000",
                                    "type": "text",
                                    "text": {"body": "Здравствуйте, лечите кроликов?"},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }

    messages = WhatsAppAdapter().parse_webhook(payload)

    assert len(messages) == 1
    assert messages[0].channel == "whatsapp"
    assert messages[0].external_user_id == "79999999999"
    assert messages[0].external_chat_id == "79999999999"
    assert messages[0].message_id == "wamid.1"
    assert messages[0].display_name == "Анна"


def test_max_adapter_parses_message_created_payload():
    payload = {
        "update_type": "message_created",
        "message": {
            "mid": "m1",
            "body": {"text": "Хочу записаться"},
            "sender": {"user_id": 42, "name": "Иван"},
            "recipient": {"chat_id": 100},
        },
    }

    messages = MaxAdapter().parse_webhook(payload)

    assert len(messages) == 1
    assert messages[0].channel == "max"
    assert messages[0].external_user_id == "42"
    assert messages[0].external_chat_id == "100"
    assert messages[0].message_id == "m1"

