from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from bot_manager.texts import ru as t

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=t.texts["btn_enter_id"])],
        [KeyboardButton(text=t.texts["btn_enter_manual"])]
        ,
        [KeyboardButton(text=t.texts["btn_ask_ai"])],
        [KeyboardButton(text=t.texts["btn_help"])]
    ],
    resize_keyboard=True
)

back_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=t.texts["btn_back"])]],
    resize_keyboard=True
)

check_again_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=t.texts["btn_check_another"])],
        [KeyboardButton(text=t.texts["btn_back"])]
    ],
    resize_keyboard=True
)