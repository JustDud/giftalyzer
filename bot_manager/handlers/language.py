from aiogram import Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from bot_manager.texts import set_language
from bot_manager.keyboards.default import get_main_menu

router = Router()


@router.message(Command("language"))
async def language_handler(message: Message, t: dict):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="English", callback_data="lang_en")],
        [InlineKeyboardButton(text="Русский", callback_data="lang_ru")]
    ])
    await message.answer(t["choose_language"], reply_markup=keyboard)


@router.callback_query(lambda c: c.data == "lang_en")
async def set_english(callback: CallbackQuery, t: dict):
    set_language(callback.from_user.id, "en")
    await callback.message.answer(t["returned_to_menu"], reply_markup=get_main_menu(t))
    await callback.message.edit_text(t["language_switched"])


@router.callback_query(lambda c: c.data == "lang_ru")
async def set_russian(callback: CallbackQuery, t: dict):
    set_language(callback.from_user.id, "ru")
    await callback.message.answer(t["returned_to_menu"], reply_markup=get_main_menu(t))
    await callback.message.edit_text(t["language_switched"])


def register(dp):
    dp.include_router(router)
