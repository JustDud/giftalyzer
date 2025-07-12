from bson import ObjectId

# Handler for /active_tickets command: show all open tickets to admin
from aiogram.filters import Command

from aiogram import Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from bot_manager.states.support_state import SupportState
from mongo import support_collection
from aiogram import F
from aiogram.fsm.context import FSMContext
import os
from bot_manager.keyboards.default import main_menu
from bot_manager.texts.ru import texts as t
from bot_manager.utils import is_admin

SUPPORT_GROUP_ID = os.getenv("SUPPORT_GROUP_ID")


router = Router()

last_ticket = support_collection.find_one(
    {"_id": {"$regex": r"^\d+$"}},
    sort=[("_id", -1)]
)
last_id = int(last_ticket["_id"]) if last_ticket else 1000
ticket_id = str(last_id + 1)


def escape_md(text: str) -> str:
    escape_chars = r"\_*[]()~`>#+-=|{}.!"
    return ''.join(f'\\{c}' if c in escape_chars else c for c in text)


# Handler: reply-to-message for support ticket replies
@router.message(lambda msg: msg.reply_to_message is not None and msg.text)
async def reply_to_support_ticket(message: Message):
    original_msg = message.reply_to_message
    lines = original_msg.text.splitlines()

    # Attempt to find ticket ID from original message
    ticket_line = next((line for line in lines if line.startswith("📨 Ticket ID:")), None)
    if not ticket_line:
        return  # not a valid ticket message

    ticket_id = ticket_line.replace("📨 Ticket ID:", "").strip(" `")

    ticket = support_collection.find_one({"_id": ticket_id})
    if not ticket:
        await message.answer(t["ticket_not_found"])
        return

    user_id = ticket["user_id"]
    try:
        clarify_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📝 Уточнить", callback_data=f"clarify_{ticket_id}")]
            ]
        )
        await message.bot.send_message(
            user_id,
            f"{t['support_reply']}:\n{message.text}",
            reply_markup=clarify_keyboard
        )
        support_collection.update_one({"_id": ticket_id}, {"$set": {"status": "closed", "admin_response": message.text}})
        await message.answer(t["reply_sent"])
    except Exception as e:
        await message.answer(f"{t['reply_failed']} {e}")



from bson import ObjectId

# Handler for /active_tickets command: show all open tickets to admin
from aiogram.filters import Command


@router.callback_query(F.data.startswith("clarify_"))
async def clarify_ticket(callback_query: CallbackQuery, state: FSMContext):
    from bot_manager.keyboards.support_keyboard import send_request_keyboard

    ticket_id = callback_query.data.replace("clarify_", "")
    ticket = support_collection.find_one({"_id": ticket_id})

    if not ticket:
        await callback_query.answer("Тикет не найден.", show_alert=True)
        return

    user_id = ticket["user_id"]

    await state.set_state(SupportState.waiting_for_description)
    await state.update_data(parent_ticket_id=ticket_id)

    await callback_query.bot.send_message(
        user_id,
        "✍️ Напишите сообщение, затем нажмите «📨 Отправить».",
        reply_markup=send_request_keyboard
    )


async def close_all_tickets(message: Message):
    if not await is_admin(message):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    result = support_collection.update_many({"status": "open"}, {"$set": {"status": "closed"}})
    await message.answer(f"✅ Закрыто {result.modified_count} тикетов.")


async def show_active_tickets(message: Message):
    if not await is_admin(message):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    tickets = list(support_collection.find({"status": "open"}).sort("_id", -1))

    if not tickets:
        await message.answer("📭 Активных тикетов нет.")
        return

    def escape_md(text: str) -> str:
        escape_chars = r"\_*[]()~`>#+-=|{}.! "
        return ''.join(f'\\{c}' if c in escape_chars else c for c in text)

    for t in tickets:
        ticket_id = t.get('ticket_id', t['_id'])
        username = t.get('username', 'N/A')
        user_id = t['user_id']
        msg = escape_md(t.get("message", ""))
        text = (
            f"📨 Ticket ID: `{ticket_id}`\n"
            f"👤 @{username} (ID: {user_id})\n"
            f"📝 {msg}"
        )
        await message.answer(text, parse_mode="Markdown")


@router.callback_query(F.data == "admin_show_active_tickets")
async def handle_show_active_tickets(callback: CallbackQuery):
    await show_active_tickets(callback.message)


@router.callback_query(F.data == "admin_close_all_tickets")
async def handle_close_all_tickets(callback: CallbackQuery):
    await close_all_tickets(callback.message)


def register(dp):
    dp.include_router(router)
