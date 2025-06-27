import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.types import Message
from aiogram.filters import Command
import logging

from keyboards import reply_kb, inline_kb
from price_analyser import estimate_ton_price

import os
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("BOT_API")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer("Привет! Пришли ссылку на подарок или его ID")
    # await message.answer("Choose:", reply_markup=reply_kb)


@dp.message()
async def handle_input(message: Message):
    text = message.text.strip()

    # Extract ID if it's a link (basic placeholder logic)
    if "ton.app" in text or "getgems.io" in text:
        # Example: parse ID from the URL
        # You'll probably need more robust logic here
        nft_id = text.split("/")[-1]
    else:
        nft_id = text

    try:
        price = estimate_ton_price(nft_id)
        await message.answer(
            f"🔍 NFT ID: `{nft_id}`\n💰 Примерная цена: `{price:.2f} TON`",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        await message.answer(f"⚠️ Не удалось оценить: {str(e)}")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())