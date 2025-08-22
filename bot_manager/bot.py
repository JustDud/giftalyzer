ALLOWED_USER_IDS = {474039722, 7866461346}
import os
import asyncio
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.types import Message, LabeledPrice, PreCheckoutQuery, BotCommand
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.session.aiohttp import AiohttpSession
import logging

from bot_manager.handlers import register_all_handlers
from middleware.i18n import I18nMiddleware

from bot_manager.texts.ru import texts as ru
from bot_manager.texts.en import texts as en

from middleware.dev_guard import DevGuardMiddleware



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

# Global message handler to restrict access during development
dp.message.middleware(DevGuardMiddleware())

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
    await bot.set_my_commands([
        BotCommand(command='start', description=ru["start_command"]),
        BotCommand(command='about', description=ru["about_command"]),
        BotCommand(command='language', description=ru["language_command"]),
        BotCommand(command='support', description=ru["support_command"]),
    ], language_code="ru")

    await bot.set_my_commands([
        BotCommand(command='start', description=en["start_command"]),
        BotCommand(command='about', description=en["about_command"]),
        BotCommand(command='language', description=en["language_command"]),
        BotCommand(command='support', description=en["support_command"]),
    ], language_code="en")


if __name__ == "__main__":
    asyncio.run(main())