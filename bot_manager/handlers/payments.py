import os
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import Router, F
from aiogram.types import Message, LabeledPrice, PreCheckoutQuery, CallbackQuery
from subscription.manager import add_subscription
from mongo import subscriptions_collection, get_all_subscriptions
from datetime import datetime, timedelta
from bot_manager.utils import is_admin
from bot_manager.states.admin_states import PromoApplyFSM
from aiogram.fsm.context import FSMContext
from bot_manager.promocodes import apply_promo, list_all_promos, finalize_promo_usage


BASE_PRICE_XTR = 10  # Base subscription price in XTR

logs_group_id = os.getenv("LOGS_GROUP_ID")

router = Router()


def has_active_subscription(user_id: int):
    sub = subscriptions_collection.find_one({"user_id": user_id})
    if not sub:
        return False, None
    if sub.get("subscribed") is True or sub.get("subscribed") == "True":
        end_date = sub.get("end_date")
        if not end_date and sub.get("start_date"):
            end_date = sub["start_date"] + timedelta(days=30)
        return True, end_date
    return False, None


async def get_subscription_info(user_id: int) -> str:
    sub = subscriptions_collection.find_one({"user_id": user_id})
    if not sub:
        return "❌ Подписка не найдена для данного пользователя."
    status = sub.get("subscribed")
    start = sub.get("start_date")
    end_date = sub.get("end_date")
    if end_date:
        end_date = end_date.strftime('%d %B %Y')
    elif start:
        end_date = (start + timedelta(days=30)).strftime('%d %B %Y')
    transactions = sub.get("transactions", [])
    transaction_id = transactions[-1]["id"] if transactions else "—"
    return (
        f"👤 ID: {user_id}\n"
        f"🟢 Статус: {status}\n"
        f"⏱ С: {start}\n"
        f"📅 До: {end_date if end_date else '—'}\n"
        f"🔁 Транзакция: {transaction_id}"
    )


@router.message(lambda msg, t: msg.text == t["btn_subscription"])
async def handle_subscription_button(message: Message, state: FSMContext, t: dict):
    active, end_date = has_active_subscription(message.from_user.id)
    if active:
        formatted_date = end_date.strftime('%d %B %Y') if end_date else "—"
        await message.answer(t["active_subscription_until"].format(date=formatted_date))
        return
    await start_promo_flow(message, t, state)


async def start_promo_flow(message: Message, t: dict, state: FSMContext):
    # Ask user if they want to use a promo code
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t["btn_skip_promo"], callback_data="skip_promo")]
    ])
    sent_msg = await message.answer(t["ask_promo_code"], reply_markup=kb)
    await state.update_data(promo_prompt_msg_id=sent_msg.message_id)
    await state.set_state(PromoApplyFSM.waiting_for_promo_code)


@router.message(PromoApplyFSM.waiting_for_promo_code)
async def process_promo_code(message: Message, state: FSMContext, t: dict):
    data = await state.get_data()
    code = message.text.strip().upper()
    user_id = message.from_user.id
    price = BASE_PRICE_XTR  # base price in XTR

    result = apply_promo(user_id, code, price)
    await state.clear()

    if "error" in result:
        try:
            await message.answer(f"❌ {result['error']}\n{t['promo_try_again_or_skip']}")
        except Exception as e:
            print(f"[ERROR] Failed to send error message in promo flow: {e}")
        return await start_promo_flow(message, t, state)

    discounted_price = result["final_price"]
    try:
        # Delete the original promo prompt message if it exists
        prompt_msg_id = data.get("promo_prompt_msg_id")
        if prompt_msg_id:
            try:
                await message.bot.delete_message(chat_id=message.chat.id, message_id=prompt_msg_id)
            except Exception:
                pass
        await message.answer(t["promo_applied"].format(discounted_price=discounted_price))
    except Exception as e:
        print(f"[ERROR] Failed to send promo_applied message: {e}")
        await message.answer("❌ Ошибка сети. Попробуйте ещё раз.")

    subscriptions_collection.update_one(
        {"user_id": user_id},
        {"$set": {"last_used_promo": {
            "promo_code": result["promo_code"],
            "final_price": discounted_price
        }}},
        upsert=True
    )

    await start_payment_cycle(message, discounted_price, t)


@router.callback_query(F.data == "skip_promo")
async def skip_promo(callback: CallbackQuery, state: FSMContext, t: dict):
    data = await state.get_data()
    await state.clear()
    await callback.answer()
    try:
        prompt_msg_id = data.get("promo_prompt_msg_id")
        if prompt_msg_id:
            await callback.message.bot.delete_message(chat_id=callback.message.chat.id, message_id=prompt_msg_id)
        else:
            await callback.message.delete()
    except Exception:
        await callback.message.edit_reply_markup(reply_markup=None)
    await start_payment_cycle(callback.message, BASE_PRICE_XTR, t)  # base price

async def start_payment_cycle(message: Message, price: float, t: dict):
    active, end_date = has_active_subscription(message.from_user.id)
    if active:
        formatted_date = end_date.strftime('%d %B %Y') if end_date else "—"
        await message.answer(t["active_subscription_until"].format(date=formatted_date))
        return
    try:
        await message.answer(t["giftalyserpro_full"], parse_mode="HTML")
    except Exception as e:
        print(f"[ERROR] Failed to send subscription info: {e}")

    refund_policy_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t["btn_refund_policy"], callback_data="refund_policy")]
    ])

    try:
        invoice_msg = await message.answer_invoice(
            title="GIFTALYSER PRO",
            description=t["giftalyserpro_invoice_description"],
            payload="month_subscription",
            currency="XTR",
            prices=[LabeledPrice(label="XTR", amount=int(price))]
        )
    except Exception as e:
        print(f"[ERROR] Failed to send invoice: {e}")
        await message.answer("❌ Ошибка при создании платежа. Попробуйте позже.")

    try:
        await message.answer(
            t["refund_policy_notice"],
            reply_markup=refund_policy_kb
        )
    except Exception as e:
        print(f"[ERROR] Failed to send refund policy notice: {e}")

@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout: PreCheckoutQuery):
    await pre_checkout.answer(ok=True)

@router.message(F.successful_payment)
async def successful_payment(message: Message, t: dict):
    add_subscription(message.from_user.id)
    charge_id = message.successful_payment.telegram_payment_charge_id
    subscriptions_collection.update_one(
        {"user_id": message.from_user.id},
        {"$push": {"transactions": {"id": charge_id, "refunded": False, "date": datetime.utcnow()}},
         "$set": {"subscribed": True, "start_date": datetime.utcnow()}},
        upsert=True
    )
    confirmation_text = t["subscription_activated"].format(charge_id=charge_id)
    await message.answer(confirmation_text)

    if logs_group_id:
        try:
            await message.bot.send_message(
                chat_id=logs_group_id,
                text=t["new_payment_log"].format(user_id=message.from_user.id, charge_id=charge_id)
            )
        except Exception as e:
            print(f"[LOG ERROR] Failed to send payment log: {e}")

    promo_data = subscriptions_collection.find_one({"user_id": message.from_user.id})
    if promo_data and promo_data.get("last_used_promo"):
        finalize_promo_usage(
            message.from_user.id,
            promo_data["last_used_promo"]["promo_code"],
            promo_data["last_used_promo"]["final_price"]
        )
        subscriptions_collection.update_one(
            {"user_id": message.from_user.id},
            {"$unset": {"last_used_promo": ""}}
        )


@router.message(F.text.startswith("/check_subs"))
async def check_subscriptions(message: Message, t: dict):
    if not await is_admin(message):
        await message.answer(t["no_admin_access"])
        return
    try:
        parts = message.text.split()
        if len(parts) == 2:
            try:
                user_id = int(parts[1])
            except ValueError:
                await message.answer(t["invalid_user_id_format"])
                return
            sub_info = await get_subscription_info(user_id)
            await message.answer(sub_info)
        else:
            subs = get_all_subscriptions()
            if not subs:
                await message.answer(t["no_subscriptions_found"])
                return

            output = ""
            for sub in subs:
                user_id = sub.get("user_id")
                status = sub.get("subscribed")
                start = sub.get("start_date")
                transaction_id = sub.get("transaction_id", "—")
                output += f"👤 ID: {user_id}\n🟢 Активна: {status}\n⏱ С: {start}\n🔁 Транзакция: {transaction_id}\n\n"

            if len(output) > 4096:
                chunks = [output[i:i+4096] for i in range(0, len(output), 4096)]
                for chunk in chunks:
                    await message.answer(chunk)
            else:
                await message.answer(output)
    except Exception as e:
        await message.answer(t["subscription_check_error"].format(error=str(e)))


@router.message(F.text.startswith("/refund"))
async def admin_refund_handler(message: Message, *args, t: dict):
    user_id = None
    charge_id = None

    if not await is_admin(message):
        await message.answer(t["no_admin_access"])
        return

    # Extract arguments from FSM or command line
    if len(args) == 2:
        try:
            user_id = int(args[0])
            charge_id = args[1]
        except ValueError:
            await message.answer(t["invalid_refund_arguments"])
            return
    else:
        parts = message.text.split()
        if len(parts) >= 3:
            try:
                user_id = int(parts[1])
                charge_id = " ".join(parts[2:])
            except Exception as e:
                await message.answer(f"❌ Ошибка при обработке команды: {e}")
                return
        else:
            await message.answer(t["refund_usage"])
            return

    try:
        sub = subscriptions_collection.find_one({"user_id": user_id})
        if not sub or not sub.get("subscribed"):
            await message.answer(t["no_active_subscription"])
            return

        transactions = sub.get("transactions", [])
        matched_tx = next((tx for tx in transactions if tx["id"] == charge_id and not tx.get("refunded")), None)
        if not matched_tx:
            await message.answer(t["transaction_id_mismatch"])
            return

        if (datetime.utcnow() - matched_tx["date"]) > timedelta(days=14):
            await message.answer(t["subscription_expired_no_refund"])
            return

        await message.bot.refund_star_payment(
            user_id=user_id,
            telegram_payment_charge_id=charge_id
        )

        subscriptions_collection.update_one(
            {"user_id": user_id, "transactions.id": charge_id},
            {"$set": {"transactions.$.refunded": True, "subscribed": False}}
        )

        await message.answer(t["subscription_refunded"].format(user_id=user_id))
        if logs_group_id:
            try:
                await message.bot.send_message(
                    chat_id=logs_group_id,
                    text=t["refund_log"].format(user_id=user_id, charge_id=charge_id)
                )
            except Exception as log_err:
                print(f"[LOG ERROR] Failed to send refund log: {log_err}")
    except Exception as e:
        await message.answer(t["refund_error"].format(error=str(e)))


@router.message(F.text.startswith("/my_promocodes"))
async def my_promocodes_handler(message: Message, t: dict):
    try:
        user_id = message.from_user.id
        promos = [p for p in list_all_promos() if p.get("owner_id") == user_id]

        if not promos:
            await message.answer("❌ У вас нет созданных промокодов.")
            return

        text = "📋 Ваши промокоды:\n"
        for p in promos:
            text += (
                f"🔹 <b>{p['code']}</b>\n"
                f"Скидка: {p['discount_percent']}%\n"
                f"Использований: {p.get('usage_count', 0)}\n"
                f"Общий доход: {p.get('total_profit', 0.0):.2f}\n"
                f"Статус: {'✅ Активен' if p.get('is_active', False) else '❌ Отключен'}\n\n"
            )

        if len(text) > 4096:
            chunks = [text[i:i+4096] for i in range(0, len(text), 4096)]
            for chunk in chunks:
                await message.answer(chunk, parse_mode="HTML")
        else:
            await message.answer(text, parse_mode="HTML")
    except Exception as e:
        print(f"[ERROR] Failed to display user's promo codes: {e}")
        await message.answer("❌ Ошибка при отображении ваших промокодов.")


@router.callback_query(F.data == "refund_policy")
async def show_refund_policy(callback_query: CallbackQuery, t: dict):
    await callback_query.message.edit_reply_markup(reply_markup=None)
    await callback_query.message.answer(t["refund_policy_text"])
    await callback_query.answer()


def register(dp):
    dp.include_router(router)
