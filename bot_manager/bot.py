import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.filters import Command
import logging

from keyboards import reply_kb, inline_kb

import os
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("BOT_API")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer("Hello! I'm your bot powered by aiogram")
    await message.answer("Choose:", reply_markup=reply_kb)


@dp.message(Command("help"))
async def help_handler(message: Message):
    await message.answer("Use /start to begin.")
    await message.answer("Choose an option:", reply_markup=inline_kb)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())