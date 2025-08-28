import os
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from bot_manager.keyboards.admin_keyboard import get_admin_keyboard, get_promocodes_keyboard
from .payments import admin_refund_handler as perform_refund
from .payments import get_subscription_info
from bot_manager.utils import is_admin
from .admin_support import close_all_tickets, show_active_tickets
from subscription.subscription_manager import get_subscription_stats
from mongo import subscriptions_collection
from datetime import timedelta, UTC

from subscription.subscription_manager import utc_now
from bot_manager.states.admin_states import RefundFSM,CheckSubsFSM,PromoStatsFSM,PromoAddFSM,PromoDeleteFSM
from bot_manager.promocodes import get_promo_stats, create_promo, disable_promo, list_all_promos
from scripts.db_updater import update_db

logs_group_id = os.getenv("LOGS_GROUP_ID")

router = Router()


@router.message(Command("admin_panel", "adm"))
async def admin_panel(message: Message, t: dict):
    if message.chat.type not in ["group", "supergroup"]:
        return
    admins = await message.bot.get_chat_administrators(message.chat.id)
    admin_ids = [admin.user.id for admin in admins]

    if message.from_user.id not in admin_ids:
        await message.answer(t["no_admin_access"])
        return

    await message.answer(t["admin_panel_activated"], reply_markup=get_admin_keyboard(t))


@router.message(Command("update_db"))
async def update_db(message: Message, t: dict):
    if not await is_admin(message):
        await message.answer(t["no_admin_access"])
        return

    await message.answer(t["db_update_started"])
    await update_db()
    await message.answer(t["db_update_finished"])


@router.callback_query(F.data == "admin_refund")
async def admin_refund_info(callback: CallbackQuery, state: FSMContext, t: dict):
    await state.set_state(RefundFSM.waiting_for_user_id)
    await state.update_data(starter_id=callback.from_user.id)
    await callback.message.answer(t["enter_user_id_refund"], parse_mode="HTML")


@router.callback_query(F.data == "admin_check_subscription")
async def admin_check_subscription(callback: CallbackQuery, state: FSMContext, t: dict):
    await state.set_state(CheckSubsFSM.waiting_for_user_id)
    await state.update_data(starter_id=callback.from_user.id)
    await callback.message.answer(t["enter_user_id_sub_check"], parse_mode="HTML")


@router.message(RefundFSM.waiting_for_user_id)
async def process_refund_user_id(message: Message, state: FSMContext, t: dict):
    data = await state.get_data()
    if message.from_user.id != data.get("starter_id"):
        return
    await state.update_data(user_id=message.text.strip())
    await state.set_state(RefundFSM.waiting_for_transaction_id)
    await message.answer(t["enter_transaction_id"], parse_mode="HTML")


@router.message(RefundFSM.waiting_for_transaction_id)
async def process_refund_transaction_id(message: Message, state: FSMContext, t: dict):
    data = await state.get_data()
    if message.from_user.id != data.get("starter_id"):
        return
    user_id = data.get("user_id")
    transaction_id = message.text.strip()

    if not await is_admin(message):
        await message.answer(t["no_admin_access"])
        await state.clear()
        return

    await perform_refund(message, int(user_id), transaction_id, t=t)
    await state.clear()


@router.message(CheckSubsFSM.waiting_for_user_id)
async def admin_checksubs_process(message: Message, state: FSMContext, t: dict):
    if not message.text:
        return
    data = await state.get_data()
    if message.from_user.id != data.get("starter_id"):
        return

    user_id = message.text.strip()

    if not await is_admin(message):
        await message.answer(t["no_admin_access"])
        await state.clear()
        return

    result = await get_subscription_info(int(user_id))
    await message.answer(result)
    await state.clear()


@router.callback_query(F.data == "admin_show_active_tickets")
async def handle_show_active_tickets(callback: CallbackQuery):
    await callback.answer()
    await show_active_tickets(callback.message)


@router.callback_query(F.data == "admin_close_all_tickets")
async def handle_close_all_tickets(callback: CallbackQuery):
    await callback.answer()
    await close_all_tickets(callback.message)


@router.callback_query(F.data == "admin_subscription_stats")
async def handle_subscription_stats(callback: CallbackQuery, t: dict):
    await callback.answer()
    total, active = await get_subscription_stats()
    await callback.message.answer(
        t["subscription_stats"].format(total=total, active=active),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_manage_promocodes")
async def admin_manage_promocodes(callback: CallbackQuery, t: dict):
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=get_promocodes_keyboard(t))


@router.callback_query(F.data == "admin_back_main")
async def admin_back_main(callback: CallbackQuery, t: dict):
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=get_admin_keyboard(t))


@router.callback_query(F.data == "admin_promocode_stats")
async def admin_promocode_stats(callback: CallbackQuery, state: FSMContext, t: dict):
    await state.set_state(PromoStatsFSM.waiting_for_promo_code)
    await state.update_data(starter_id=callback.from_user.id)
    await callback.message.answer(t["enter_promocode_for_stats"], parse_mode="HTML")


@router.callback_query(F.data == "admin_list_promocodes")
async def admin_list_promocodes(callback: CallbackQuery, t: dict):
    try:
        promos = await list_all_promos()
        if not promos:
            await callback.message.answer(t["no_promocodes_found"])
            return

        text = t["promocodes_list_header"] + "\n"
        for p in promos:
            text += (
                f"🔹 <b>{p['code']}</b> | "
                f"{t['owner']} {p['owner_id']} | "
                f"{t['discount']} {p['discount_percent']}% | "
                f"{t['profit']} {p.get('total_profit', 0):.2f} | "
                f"{'✅' if p.get('is_active') else '❌'}\n"
                f"➡️ {t.get('income_percentage','Доход владельца')} {p.get('owner_profit_percent', 0)}%\n"
            )

        await callback.message.answer(text, parse_mode="HTML")
    except Exception as e:
        print(f"[ERROR] Failed to list promo codes: {e}")
        await callback.message.answer(t["operation_error"])


@router.message(PromoStatsFSM.waiting_for_promo_code)
async def process_promo_stats(message: Message, state: FSMContext, t: dict):
    data = await state.get_data()
    if message.from_user.id != data.get("starter_id"):
        return

    code = message.text.strip().upper()
    stats = await get_promo_stats(code)
    await state.clear()

    print(f"[DEBUG] Promo stats for {code}: {stats}")  # Log the stats for debugging

    if not stats:
        await message.answer(t["promocode_not_found"].format(code=code))
        return

    try:
        await message.answer(
            t["promocode_stats"].format(
                code=code,
                usage=stats.get("usage_count", 0),
                total_profit=stats.get("total_profit", 0.0),
                active="✅" if stats.get("is_active", False) else "❌"
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"[ERROR] Failed to send promo stats for {code}: {e}")
        await message.answer(t["operation_error"])


@router.callback_query(F.data == "admin_add_promocode")
async def admin_add_promocode(callback: CallbackQuery, state: FSMContext, t: dict):
    await state.set_state(PromoAddFSM.waiting_for_code)
    await state.update_data(starter_id=callback.from_user.id)
    await callback.message.answer(t["enter_promocode_code"], parse_mode="HTML")


@router.message(PromoAddFSM.waiting_for_code)
async def process_add_code(message: Message, state: FSMContext, t: dict):
    try:
        if message.from_user.id != (await state.get_data()).get("starter_id"):
            return
        await state.update_data(code=message.text.strip().upper())
        await state.set_state(PromoAddFSM.waiting_for_owner_id)
        await message.answer(t["enter_promocode_owner"], parse_mode="HTML")
    except Exception as e:
        print(f"[ERROR] Failed at add code step: {e}")
        await message.answer(t["operation_error"])


@router.message(PromoAddFSM.waiting_for_owner_id)
async def process_add_owner(message: Message, state: FSMContext, t: dict):
    try:
        if message.from_user.id != (await state.get_data()).get("starter_id"):
            return
        await state.update_data(owner_id=int(message.text.strip()))
        await state.set_state(PromoAddFSM.waiting_for_discount)
        await message.answer(t["enter_promocode_discount"], parse_mode="HTML")
    except Exception as e:
        print(f"[ERROR] Failed at add owner step: {e}")
        await message.answer(t["operation_error"])


@router.message(PromoAddFSM.waiting_for_discount)
async def process_add_discount(message: Message, state: FSMContext, t: dict):
    if message.from_user.id != (await state.get_data()).get("starter_id"):
        return
    try:
        discount = float(message.text.strip())
        if not 0 <= discount <= 100:
            raise ValueError
    except ValueError:
        await message.answer(t["operation_error"])
        return
    await state.update_data(discount=discount)
    await state.set_state(PromoAddFSM.waiting_for_profit)
    await message.answer(t["enter_promocode_profit"], parse_mode="HTML")


@router.message(PromoAddFSM.waiting_for_profit)
async def process_add_profit(message: Message, state: FSMContext, t: dict):
    if message.from_user.id != (await state.get_data()).get("starter_id"):
        return
    try:
        profit = float(message.text.strip())
        if not 0 <= profit <= 100:
            raise ValueError
    except ValueError:
        await message.answer(t["operation_error"])
        return
    await state.update_data(profit=profit)
    await state.set_state(PromoAddFSM.waiting_for_single_use)
    await message.answer(t["enter_promocode_single_use"], parse_mode="HTML")


@router.message(PromoAddFSM.waiting_for_single_use)
async def process_add_single_use(message: Message, state: FSMContext, t: dict):
    data = await state.get_data()
    if message.from_user.id != data.get("starter_id"):
        return
    try:
        single_use_flag = int(message.text.strip())
        if single_use_flag not in (0, 1):
            raise ValueError
    except ValueError:
        await message.answer(t["operation_error"])
        return

    promo = await create_promo(
        data["code"],
        data["owner_id"],
        data["discount"],
        data["profit"],
        single_use_flag == 1
    )
    await state.clear()
    await message.answer(t["promocode_created"].format(code=promo["code"]), parse_mode="HTML")


@router.callback_query(F.data == "admin_delete_promocode")
async def admin_delete_promocode(callback: CallbackQuery, state: FSMContext, t: dict):
    await state.set_state(PromoDeleteFSM.waiting_for_code)
    await state.update_data(starter_id=callback.from_user.id)
    await callback.message.answer(t["enter_promocode_for_delete"], parse_mode="HTML")


@router.message(PromoDeleteFSM.waiting_for_code)
async def process_delete_promo(message: Message, state: FSMContext, t: dict):
    try:
        data = await state.get_data()
        if message.from_user.id != data.get("starter_id"):
            return
        code = message.text.strip().upper()
        ok = await disable_promo(code)
        await state.clear()
        if ok:
            await message.answer(t["promocode_disabled"].format(code=code))
        else:
            await message.answer(t["promocode_not_found"].format(code=code))
    except Exception as e:
        print(f"[ERROR] Failed to delete promo code: {e}")
        await message.answer("❌ Ошибка при удалении промокода.")


@router.message(Command("force_refund"))
async def admin_force_refund(message: Message, t: dict):
    if not await is_admin(message):
        await message.answer(t["no_admin_access"])
        return

    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("Usage: /force_refund <user_id> <charge_id>")
        return

    try:
        user_id = int(parts[1])
        charge_id = parts[2]
    except ValueError:
        await message.answer("Invalid arguments.")
        return

    try:
        await message.bot.refund_star_payment(
            user_id=user_id,
            telegram_payment_charge_id=charge_id
        )
        await subscriptions_collection.update_one(
            {"user_id": user_id, "transactions.id": charge_id},
            {"$set": {"transactions.$.refunded": True}}
        )
        await message.answer(f"✅ Forced refund processed for user {user_id}, charge {charge_id}")
        if logs_group_id:
            try:
                await message.bot.send_message(
                    chat_id=logs_group_id,
                    text=f"🔁 Forced refund by admin: user {user_id}, charge {charge_id}"
                )
            except Exception as e:
                print(f"[LOG ERROR] Failed to send forced refund log: {e}")
    except Exception as e:
        await message.answer(f"❌ Error while forcing refund: {e}")


@router.message(Command("force_subscribe"))
async def admin_force_subscribe(message: Message, t: dict):
    if not await is_admin(message):
        await message.answer(t["no_admin_access"])
        return

    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("Usage: /force_subscribe <user_id> <days>")
        return

    try:
        user_id = int(parts[1])
        days = int(parts[2])
    except ValueError:
        await message.answer("Invalid arguments.")
        return

    end_date = utc_now() + timedelta(days=days)
    await subscriptions_collection.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "subscribed": True,
                "start_date": utc_now(),
                "end_date": end_date
            }
        },
        upsert=True
    )
    await message.answer(f"✅ Forced subscription activated for {user_id} for {days} days.")
    if logs_group_id:
        try:
            await message.bot.send_message(
                chat_id=logs_group_id,
                text=f"✅ Forced subscription by admin: user {user_id}, {days} days"
            )
        except Exception as e:
            print(f"[LOG ERROR] Failed to send forced subscription log: {e}")


@router.message(Command("force_cancel"))
async def admin_force_cancel(message: Message, t: dict):
    if not await is_admin(message):
        await message.answer(t["no_admin_access"])
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Usage: /force_cancel <user_id>")
        return

    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer("Invalid user_id.")
        return

    await subscriptions_collection.update_one(
        {"user_id": user_id},
        {"$set": {
            "subscribed": False,
            "end_date": utc_now()
        }},
    )
    await message.answer(f"✅ Subscription for user {user_id} has been forcibly cancelled.")
    if logs_group_id:
        try:
            await message.bot.send_message(
                chat_id=logs_group_id,
                text=f"⛔ Forced subscription cancellation by admin: user {user_id}"
            )
        except Exception as e:
            print(f"[LOG ERROR] Failed to send forced cancellation log: {e}")


def register(dp):
    dp.include_router(router)