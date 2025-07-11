from aiogram import Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

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
        support_collection.update_one({"_id": ticket_id}, {"$set": {"status": "replied", "admin_response": message.text}})
        await message.answer(t["reply_sent"])
    except Exception as e:
        await message.answer(f"{t['reply_failed']} {e}")


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


# @router.message(F.text.lower().in_([t["btn_help"].lower(), "/support"]))
# async def support_entry(message: Message, state: FSMContext):
#     # Ensure ticket_counter is ahead of existing tickets
#     existing_max = support_collection.find_one(
#         {"_id": {"$regex": r"^\d+$"}},
#         sort=[("_id", -1)]
#     )
#     if existing_max:
#         current_max = int(existing_max["_id"])
#         counter_doc = support_collection.find_one({"_id": "ticket_counter"}) or {"seq": 0}
#         current_seq = counter_doc.get("seq", 0)
#         if current_seq < (current_max - 1000 + 1):
#             support_collection.update_one(
#                 {"_id": "ticket_counter"},
#                 {"$set": {"seq": current_max - 1000 + 1}},
#                 upsert=True
#             )
#
#     await state.set_state(SupportState.waiting_for_description)
#     await state.update_data(parent_ticket_id=None)
#     await message.answer(t["prompt_support_message"])


def register(dp):
    dp.include_router(router)