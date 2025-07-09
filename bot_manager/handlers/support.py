from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from bot_manager.states.support_state import SupportState
from mongo import support_collection
from bot_manager.texts.ru import texts as t
from pymongo import ReturnDocument
from bot_manager.keyboards.default import main_menu

import os

SUPPORT_GROUP_ID = os.getenv("SUPPORT_GROUP_ID")

router = Router()


@router.message(F.text == t["btn_help"])
async def support_entry(message: Message, state: FSMContext):
    await message.answer(t["prompt_support_message"])
    await state.set_state(SupportState.waiting_for_description)


@router.message(F.text.lower() == "/support")
async def support_entry_command(message: Message, state: FSMContext):
    await message.answer(t["prompt_support_message"])
    await state.set_state(SupportState.waiting_for_description)


@router.message(SupportState.waiting_for_description)
async def handle_support_message(message: Message, state: FSMContext):
    # Atomically increment ticket ID
    counter = support_collection.find_one_and_update(
        {"_id": "ticket_counter"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )
    ticket_id = str(1000 + counter["seq"])

    user_data = {
        "_id": ticket_id,
        "user_id": message.from_user.id,
        "username": message.from_user.username,
        "message": message.text,
        "status": "open",
        "created_at": message.date.isoformat()
    }

    support_collection.insert_one(user_data)

    try:
        user_line = (
            f"👤 User: @{message.from_user.username} (ID: {message.from_user.id})"
            if message.from_user.username
            else f"👤 User ID: {message.from_user.id}"
        )

        await message.bot.send_message(
            SUPPORT_GROUP_ID,
            f"📨 Ticket ID: `{ticket_id}`\n{user_line}\n📝 Message: {message.text}"
        )
    except Exception as e:
        await message.answer(f"❌ Failed to send to group: {e}")

    await message.answer(f"{t['support_received']}\n🆔 Ticket ID: {ticket_id}")
    await state.clear()


def register(dp):
    dp.include_router(router)
