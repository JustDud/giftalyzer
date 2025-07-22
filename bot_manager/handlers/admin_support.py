import os
from aiogram import Router
from aiogram.types import Message, CallbackQuery
from bot_manager.states.support_state import SupportState
from mongo import support_collection
from aiogram import F
from aiogram.fsm.context import FSMContext
from bot_manager.keyboards.support_keyboard import get_send_request_keyboard, get_clarify_kb
from bot_manager.utils import is_admin

SUPPORT_GROUP_ID = os.getenv("SUPPORT_GROUP_ID")

router = Router()


# These will be initialized asynchronously
last_ticket = None
last_id = 1000
ticket_id = None


async def init_last_ticket():
    global last_ticket, last_id, ticket_id
    last_ticket = await support_collection.find_one(
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
async def reply_to_support_ticket(message: Message, t: dict):
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
        clarify_keyboard = get_clarify_kb(t, ticket_id)
        await message.bot.send_message(
            user_id,
            f"{t['support_reply']}:\n{message.text}",
            reply_markup=clarify_keyboard
        )
        support_collection.update_one({"_id": ticket_id}, {"$set": {"status": "closed", "admin_response": message.text}})
        await message.answer(t["reply_sent"])
    except Exception as e:
        await message.answer(f"{t['reply_failed']} {e}")


@router.callback_query(F.data.startswith("clarify_"))
async def clarify_ticket(callback_query: CallbackQuery, state: FSMContext, t: dict):

    ticket_id = callback_query.data.replace("clarify_", "")
    ticket = support_collection.find_one({"_id": ticket_id})

    if not ticket:
        await callback_query.answer(t["ticket_not_found"], show_alert=True)
        return

    user_id = ticket["user_id"]

    await state.set_state(SupportState.waiting_for_description)
    await state.update_data(parent_ticket_id=ticket_id)

    await callback_query.bot.send_message(
        user_id,
        t["write_and_submit"],
        reply_markup=get_send_request_keyboard(t)
    )
    await callback_query.message.edit_reply_markup(reply_markup=None)


async def close_all_tickets(message: Message, t: dict):
    if not await is_admin(message):
        await message.answer(t["no_admin_access"])
        return
    result = support_collection.update_many({"status": "open"}, {"$set": {"status": "closed"}})
    await message.answer(t["tickets_closed"].format(count=result.modified_count))


async def show_active_tickets(message: Message, t: dict):
    if not await is_admin(message):
        await message.answer(t["no_admin_access"])
        return
    tickets = list(support_collection.find({"status": "open"}).sort("_id", -1))

    if not tickets:
        await message.answer(t["no_active_tickets"])
        return

    for ticket in tickets:
        ticket_id = ticket.get('ticket_id', ticket['_id'])
        username = ticket.get('username', 'N/A')
        user_id = ticket['user_id']
        msg = escape_md(ticket.get("message", ""))
        text = (
            f"📨 Ticket ID: `{ticket_id}`\n"
            f"👤 @{username} (ID: {user_id})\n"
            f"📝 {msg}"
        )
        await message.answer(text, parse_mode="Markdown")


@router.callback_query(F.data == "admin_show_active_tickets")
async def handle_show_active_tickets(callback: CallbackQuery, t: dict):
    await show_active_tickets(callback.message, t)


@router.callback_query(F.data == "admin_close_all_tickets")
async def handle_close_all_tickets(callback: CallbackQuery, t: dict):
    await close_all_tickets(callback.message, t)


def register(dp):
    dp.include_router(router)
