from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot_manager.states.support_state import SupportState
from mongo import support_collection
from pymongo import ReturnDocument
from bot_manager.keyboards.default import get_main_menu
from bot_manager.keyboards.support_keyboard import get_send_request_keyboard

import os

SUPPORT_GROUP_ID = os.getenv("SUPPORT_GROUP_ID")

router = Router()


@router.message(lambda message, t: message.text in [t["btn_help"], "/support"])
async def support_entry(message: Message, state: FSMContext, t: dict):
    await state.set_state(SupportState.waiting_for_description)
    await state.update_data(parent_ticket_id=None)
    await message.answer(t["support_write_message"], reply_markup=get_send_request_keyboard(t))


@router.message(lambda message, t: message.text == t["btn_back"], SupportState.waiting_for_description)
async def handle_back_button(message: Message, state: FSMContext, t: dict):
    await state.clear()
    await message.answer(t["support_back_to_main"], reply_markup=get_main_menu(t))


@router.message(SupportState.waiting_for_description)
async def handle_support_message(message: Message, state: FSMContext, t: dict):
    if message.text == t["btn_back"]:
        await state.clear()
        await message.answer(t["support_back_to_main"], reply_markup=get_main_menu(t))
        return

    if message.text == t["btn_confirm"]:
        data = await state.get_data()
        user_text = data.get("pending_message")
        if not user_text:
            await message.answer(t["support_confirm_error"])
            return

        # Generate ticket ID
        existing_max = support_collection.find_one(
            {"_id": {"$regex": r"^\d+$"}},
            sort=[("_id", -1)]
        )
        if existing_max:
            current_max = int(existing_max["_id"])
            counter_doc = support_collection.find_one({"_id": "ticket_counter"}) or {"seq": 0}
            current_seq = counter_doc.get("seq", 0)
            if current_seq < (current_max - 1000 + 1):
                support_collection.update_one(
                    {"_id": "ticket_counter"},
                    {"$set": {"seq": current_max - 1000 + 1}},
                    upsert=True
                )
        counter = support_collection.find_one_and_update(
            {"_id": "ticket_counter"},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER
        )
        ticket_id = str(1000 + counter["seq"])

        parent_ticket_id = data.get("parent_ticket_id")

        user_data = {
            "_id": ticket_id,
            "user_id": message.from_user.id,
            "username": message.from_user.username,
            "message": user_text,
            "status": "open",
            "created_at": message.date.isoformat(),
        }

        if parent_ticket_id:
            user_data["parent_ticket_id"] = parent_ticket_id

        support_collection.insert_one(user_data)

        try:
            user_line = (
                f"👤 User: @{message.from_user.username} (ID: {message.from_user.id})"
                if message.from_user.username
                else f"👤 User ID: {message.from_user.id}"
            )

            thread_text = ""
            if parent_ticket_id:
                thread = []
                current_id = parent_ticket_id
                while current_id:
                    parent = support_collection.find_one({"_id": current_id})
                    if parent:
                        thread.append(f"[{parent['_id']}] {parent['message']}")
                        current_id = parent.get("parent_ticket_id")
                    else:
                        break
                thread_text = t["support_thread_history"] + "\n" + "\n".join(reversed(thread)) + "\n\n"

            full_message = (
                f"{thread_text}"
                f"📨 Ticket ID: `{ticket_id}`\n{user_line}\n📝 Message: {user_text}"
            )

            await message.bot.send_message(SUPPORT_GROUP_ID, full_message)
        except Exception as e:
            await message.answer(t["support_send_error"])

        await message.answer(f"{t['support_received']}\n🆔 Ticket ID: {ticket_id}", reply_markup=get_main_menu(t))
        await state.clear()
        return

    # Save user message for future confirmation
    await state.update_data(pending_message=message.text)
    await message.answer(
        t["support_confirm_prompt"],
        reply_markup=get_send_request_keyboard(t)
    )


@router.callback_query(F.data.startswith("clarify_"))
async def clarify_ticket(callback_query: CallbackQuery, state: FSMContext, t: dict):
    ticket_id = callback_query.data.replace("clarify_", "")
    await state.set_state(SupportState.waiting_for_description)
    await state.update_data(parent_ticket_id=ticket_id)
    await callback_query.message.answer(t["support_write_message"], reply_markup=get_send_request_keyboard(t))
    await callback_query.answer()


def register(dp):
    dp.include_router(router)
