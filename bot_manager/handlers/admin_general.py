from typing import Awaitable

from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardRemove, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from bot_manager.keyboards.admin_keyboard import admin_keyboard
from bot_manager.handlers.payments import admin_refund_handler as perform_refund
from bot_manager.handlers.payments import get_subscription_info
from bot_manager.utils import is_admin
from bot_manager.handlers.admin_support import close_all_tickets, show_active_tickets
from subscription.manager import get_subscription_stats

router = Router()

class RefundFSM(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_transaction_id = State()

# New FSM for checking subscriptions
class CheckSubsFSM(StatesGroup):
    waiting_for_user_id = State()

@router.message(Command("admin_panel", "adm"))
async def admin_panel(message: Message):
    if message.chat.type not in ["group", "supergroup"]:
        return
    admins = await message.bot.get_chat_administrators(message.chat.id)
    admin_ids = [admin.user.id for admin in admins]

    if message.from_user.id not in admin_ids:
        await message.answer("❌ У вас нет доступа к админ-панели.")
        return

    await message.answer("🛠 Админ-панель активирована.\nВыберите действие ниже:", reply_markup=admin_keyboard)


@router.callback_query(F.data == "admin_refund")
async def admin_refund_info(callback: CallbackQuery, state: FSMContext):
    await state.set_state(RefundFSM.waiting_for_user_id)
    await state.update_data(starter_id=callback.from_user.id)
    await callback.message.answer("Введите <b>User ID</b> для возврата:", parse_mode="HTML")


# New callback handler for checking subscriptions (restored for "admin_check_subscription")
@router.callback_query(F.data == "admin_check_subscription")
async def admin_check_subscription(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CheckSubsFSM.waiting_for_user_id)
    await state.update_data(starter_id=callback.from_user.id)
    await callback.message.answer("🔍 Введите <b>User ID</b> для проверки подписки:", parse_mode="HTML")


@router.message(RefundFSM.waiting_for_user_id)
async def process_refund_user_id(message: Message, state: FSMContext):
    data = await state.get_data()
    if message.from_user.id != data.get("starter_id"):
        return
    await state.update_data(user_id=message.text.strip())
    await state.set_state(RefundFSM.waiting_for_transaction_id)
    await message.answer("Теперь введите <b>Transaction ID</b>:", parse_mode="HTML")


@router.message(RefundFSM.waiting_for_transaction_id)
async def process_refund_transaction_id(message: Message, state: FSMContext):
    data = await state.get_data()
    if message.from_user.id != data.get("starter_id"):
        return
    user_id = data.get("user_id")
    transaction_id = message.text.strip()

    if not await is_admin(message):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        await state.clear()
        return

    await perform_refund(message, int(user_id), transaction_id)
    await state.clear()


# New message handler for CheckSubsFSM
@router.message(CheckSubsFSM.waiting_for_user_id)
async def admin_checksubs_process(message: Message, state: FSMContext):
    if not message.text:
        return
    data = await state.get_data()
    if message.from_user.id != data.get("starter_id"):
        return

    user_id = message.text.strip()

    if not await is_admin(message):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        await state.clear()
        return

    result = await get_subscription_info(int(user_id))
    await message.answer(result)
    await state.clear()


@router.callback_query(F.data == "admin_show_active_tickets")
async def handle_show_active_tickets(callback: CallbackQuery):
    await callback.answer()  # Acknowledge the callback
    print("🔧 Active tickets callback triggered")
    await show_active_tickets(callback.message)

@router.callback_query(F.data == "admin_close_all_tickets")
async def handle_close_all_tickets(callback: CallbackQuery):
    await callback.answer()  # Acknowledge the callback
    await close_all_tickets(callback.message)


# New callback handler for subscription stats
@router.callback_query(F.data == "admin_subscription_stats")
async def handle_subscription_stats(callback: CallbackQuery):
    await callback.answer()
    total, active = get_subscription_stats()
    await callback.message.answer(
        f"📊 <b>Subscription Stats</b>:\n"
        f"👥 Total: <b>{total}</b>\n"
        f"✅ Active: <b>{active}</b>",
        parse_mode="HTML"
    )


def register(dp):
    dp.include_router(router)