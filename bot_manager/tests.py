from mongo import nfts_collection

def get_unique_backdrops() -> list:
    """
    Extract all unique, non-empty backdrops from the nfts collection.
    Returns:
        list: A sorted list of unique backdrop values.
    """
    unique_backdrops = nfts_collection.distinct("backdrop")
    return sorted([b for b in unique_backdrops if b])


if __name__ == "__main__":
    backdrops = get_unique_backdrops()
    print("Unique Backdrops:", backdrops)

# import asyncio
# from aiogram import Bot, Dispatcher, F, types
# from aiogram.enums import ParseMode
# from aiogram.types import Message, LabeledPrice, PreCheckoutQuery
# from aiogram.filters import Command
# import logging
#
# from subscription.manager import add_subscription
#
# import os
#
#
# from bot_manager.keyboards import reply_kb, inline_kb
# from analyser.price_analyser import estimate_ton_price
#
# from dotenv import load_dotenv
# load_dotenv()
#
# BOT_TOKEN = os.getenv("BOT_API")
#
# os.makedirs("logs", exist_ok=True)
#
# logging.basicConfig(
#     level=logging.INFO,
#     filename="logs/bot.log",
#     format="%(asctime)s - %(levelname)s - %(message)s"
# )
#
# bot = Bot(token=BOT_TOKEN)
# dp = Dispatcher()
#
#
# @dp.message(Command("start"))
# async def start_handler(message: Message):
#     await message.answer("Привет! Пришли ссылку на подарок или его ID")
#     # await message.answer("Choose:", reply_markup=reply_kb)
#
#
# @dp.message(Command("payment"))
# async def payment_handler(message: Message) -> None:
#     await message.answer_invoice(
#         title="Plus Plan",
#         description="Payment for a Plus Plan",
#         payload="month_subscription",
#         currency="XTR",
#         prices=[LabeledPrice(label="XTR", amount=1)],
#     )
#
#
# @dp.pre_checkout_query
# async def pre_checkout_handler(event: PreCheckoutQuery) -> None:
#     await event.answer(True)
#
#
# @dp.message(F.successful.payment)
# async def successful_payment(message: Message) -> None:
#     await message.answer("The payment has been successful")
#     add_subscription(message.from_user.id)
#     await bot.refund_star_payment(
#         message.from_user.id, message.successful_payment.telegram_payment_charge_id
#     )
#
#
# @dp.message()
# async def price_handler(message: Message):
#     text = message.text.strip()
#
#     # Extract ID if it's a link (basic placeholder logic)
#     if "ton.app" in text or "getgems.io" in text:
#         # Example: parse ID from the URL
#         # You'll probably need more robust logic here
#         nft_id = text.split("/")[-1]
#     else:
#         nft_id = text
#
#     try:
#         price = estimate_ton_price(nft_id)
#         await message.answer(
#             f"🔍 NFT ID: `{nft_id}`\n💰 Примерная цена: `{price:.2f} TON`",
#             parse_mode=ParseMode.MARKDOWN,
#         )
#     except Exception as e:
#         await message.answer(f"⚠️ Не удалось оценить: {str(e)}")
#
#
# async def main():
#     await dp.start_polling(bot)
#
#
# if __name__ == "__main__":
#     asyncio.run(main())
#
#
#
# from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
#
# # Reply keyboard
# reply_kb = ReplyKeyboardMarkup(
#     keyboard=[
#         [KeyboardButton(text="Option 1")],
#         [KeyboardButton(text="Option 2"), KeyboardButton(text="Option 3")]
#     ],
#     resize_keyboard=True
# )
#
# # Inline keyboard
# inline_kb = InlineKeyboardMarkup(inline_keyboard=[
#     [InlineKeyboardButton(text="Google", url="https://google.com")],
#     [InlineKeyboardButton(text="Say Hello", callback_data="say_hello")]
# ])
#
# # Remove inline keyboard
# remove_inline_kb = InlineKeyboardMarkup(inline_keyboard=[])