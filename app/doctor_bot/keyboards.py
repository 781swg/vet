from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def lead_keyboard(lead_id: int) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="Взять в работу", callback_data=f"lead:take:{lead_id}"),
            InlineKeyboardButton(text="Записан", callback_data=f"lead:booked:{lead_id}"),
        ],
        [
            InlineKeyboardButton(text="Перезвонить позже", callback_data=f"lead:callback:{lead_id}"),
            InlineKeyboardButton(text="Закрыть", callback_data=f"lead:close:{lead_id}"),
        ],
        [
            InlineKeyboardButton(text="Не наш клиент", callback_data=f"lead:lost:{lead_id}"),
            InlineKeyboardButton(text="История", callback_data=f"lead:history:{lead_id}"),
            InlineKeyboardButton(text="Клиент", callback_data=f"lead:client:{lead_id}"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def reports_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Отчет сегодня", callback_data="report:daily"),
                InlineKeyboardButton(text="Отчет неделя", callback_data="report:weekly"),
                InlineKeyboardButton(text="Отчет месяц", callback_data="report:monthly"),
            ]
        ]
    )
