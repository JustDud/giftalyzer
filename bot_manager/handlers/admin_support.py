from aiogram import Router
from aiogram.types import Message

from bot_manager.states.support_state import SupportState
from mongo import support_collection
from aiogram import F
from aiogram.fsm.context import FSMContext
import os
from bot_manager.keyboards.default import main_menu
from bot_manager.texts.ru import texts as t


SUPPORT_GROUP_ID = os.getenv("SUPPORT_GROUP_ID")


router = Router()

last_ticket = support_collection.find_one(
    {"_id": {"$regex": r"^\d+$"}},
    sort=[("_id", -1)]
)
last_id = int(last_ticket["_id"]) if last_ticket else 1000
ticket_id = str(last_id + 1)


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
        await message.bot.send_message(user_id, f"{t['support_reply']}:\n{message.text}")
        support_collection.update_one({"_id": ticket_id}, {"$set": {"status": "replied", "admin_response": message.text}})
        await message.answer(t["reply_sent"])
    except Exception as e:
        await message.answer(f"{t['reply_failed']} {e}")





# @router.message(F.text.lower() == "🆘 помощь")
# async def support_entry(message: Message, state: FSMContext):
#     await message.answer(t["prompt_support_message"])
#     await state.set_state(SupportState.waiting_for_description)



def register(dp):
    dp.include_router(router)