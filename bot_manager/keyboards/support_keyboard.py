from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_clarify_kb(t, ticket_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t["clarify"], callback_data=f"clarify_{ticket_id}")]
        ]
    )


def get_send_request_keyboard(t):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t["btn_confirm"])],
            [KeyboardButton(text=t["btn_back"])]
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        selective=True
    )