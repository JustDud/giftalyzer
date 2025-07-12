from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔄 Проверить подписку")],
        [KeyboardButton(text="💸 Рефанд")]
    ],
    resize_keyboard=True,
    selective=True
)