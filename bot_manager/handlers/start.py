from aiogram import types, Router
from aiogram.filters import CommandStart
from bot_manager.keyboards.default import main_menu
from bot_manager.texts import ru as t

router = Router()


@router.message(CommandStart())
async def start_handler(message: types.Message):
    await message.answer(t.texts["start"], reply_markup=main_menu)


def register(dp):
    dp.include_router(router)
