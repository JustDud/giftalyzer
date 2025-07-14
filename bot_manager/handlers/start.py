from aiogram import types, Router
from aiogram.filters import CommandStart
from bot_manager.keyboards.default import get_main_menu

router = Router()


@router.message(CommandStart())
async def start_handler(message: types.Message, t: dict):
    await message.answer(t["start"], reply_markup=get_main_menu(t))


def register(dp):
    dp.include_router(router)
