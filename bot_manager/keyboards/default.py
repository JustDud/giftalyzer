from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔎 Ввести ID подарка")],
        [KeyboardButton(text="✍️ Ввести вручную (тип, фон..)")]
        ,
        [KeyboardButton(text="🤖 Задать вопрос AI")],
        [KeyboardButton(text="🆘 Помощь")]
    ],
    resize_keyboard=True
)

back_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🔙 Назад")]],
    resize_keyboard=True
)