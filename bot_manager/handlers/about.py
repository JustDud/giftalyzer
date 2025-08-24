from aiogram import Router, F
from aiogram.types import Message

router = Router()


@router.message(F.text == "/about")
async def about_handler(message: Message):
    about_text = (
        "🤖 <b>Giftalyzer Бот</b>\n\n"
        "Добро пожаловать в Giftalyzer! 🎁\n\n"
        "С помощью Giftalyzer вы можете:\n"
        "• Анализировать и оценивать Telegram подарки\n"
        "• Проверять редкость, цены и другие NFT-статистики\n"
        "• Быть в курсе последних трендов подарков TON\n\n"
        "📢 <b>Канал:</b> https://t.me/giftalyzer\n"
    )
    await message.answer(about_text, parse_mode="HTML")


def register(dp):
    dp.include_router(router)
