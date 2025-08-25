import os
import asyncio
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import Message, LabeledPrice, PreCheckoutQuery, BotCommand
from aiogram.client.session.aiohttp import AiohttpSession
import logging
from bot_manager.handlers import register_all_handlers
from bot_manager.middleware.i18n import I18nMiddleware
from bot_manager.texts.ru import texts as ru
from bot_manager.texts.en import texts as en
from bot_manager.middleware.dev_guard import DevGuardMiddleware
from bot_manager.middleware.error_handler import global_error_handler
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage


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
        # logging.FileHandler("logs/bot.log", mode='a'),
        logging.StreamHandler()
    ]
)

session = AiohttpSession(timeout=30)  # default is 10
bot = Bot(token=BOT_TOKEN, session=session)
dp = Dispatcher()

dp.update.middleware(I18nMiddleware())
dp.message.middleware(DevGuardMiddleware())
dp.errors.register(global_error_handler)


async def run_bot():
    await set_commands()
    logging.info("Bot is starting...")
    register_all_handlers(dp)
    await dp.start_polling(bot)


async def set_commands():
    await bot.set_my_commands([
        BotCommand(command='start', description=ru["start_command"]),
        BotCommand(command='about', description=ru["about_command"]),
        BotCommand(command='support', description=ru["support_command"]),
    ], language_code="ru")

    await bot.set_my_commands([
        BotCommand(command='start', description=en["start_command"]),
        BotCommand(command='about', description=en["about_command"]),
        BotCommand(command='support', description=en["support_command"]),
    ], language_code="en")


#BotCommand(command='language', description=en["language_command"]),

