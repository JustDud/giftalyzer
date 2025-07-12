from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot_manager.texts.ru import texts as t

clarify_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text=t["clarify"], callback_data="clarify_ticket")]
])


send_request_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📨 Подтвердить")],
        [KeyboardButton(text="🔙 Назад")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
    selective=True
)