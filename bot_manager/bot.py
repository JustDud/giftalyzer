import os
import asyncio
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.types import Message, LabeledPrice, PreCheckoutQuery, BotCommand
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
import logging

from bot_manager.handlers import register_all_handlers

from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("BOT_API")

os.makedirs("logs", exist_ok=True)

# Remove any default handlers
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# Set up logging to file and terminal
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/bot.log", mode='a'),
        logging.StreamHandler()
    ]
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# @dp.message(Command("start"))
# async def start_handler(message: Message):
#     await message.answer("Привет! Пришли ссылку на подарок или его ID")
#     # await message.answer("Choose:", reply_markup=reply_kb)


async def main():
    await set_commands()
    logging.info("🚀 Bot is starting...")
    register_all_handlers(dp)
    await dp.start_polling(bot)


async def set_commands():
    commands = [
        BotCommand(command='start', description='Run the bot'),
        BotCommand(command='help', description='help')
    ]
    await bot.set_my_commands(commands)


if __name__ == "__main__":
    asyncio.run(main())