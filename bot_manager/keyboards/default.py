from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_menu(t):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t["btn_enter_id"])],
            [KeyboardButton(text=t["btn_enter_manual"])],
            [KeyboardButton(text=t["btn_ask_ai"])],
            [KeyboardButton(text=t["btn_subscription"])],
            [KeyboardButton(text=t["btn_help"])]
        ],
        resize_keyboard=True
    )

def get_back_keyboard(t):
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t["btn_back"])]],
        resize_keyboard=True
    )

def get_check_again_keyboard(t):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t["btn_check_another"])],
            [KeyboardButton(text=t["btn_back"])]
        ],
        resize_keyboard=True
    )