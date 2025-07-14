from aiogram.types import Message
from aiogram import Router, F
from aiogram.types import Message, LabeledPrice, PreCheckoutQuery
from subscription.manager import add_subscription
from mongo import get_all_subscriptions
from mongo import subscriptions_collection
from datetime import datetime, timedelta
import os
from bot_manager.utils import is_admin

logs_group_id = os.getenv("LOGS_GROUP_ID")

router = Router()

async def get_subscription_info(user_id: int) -> str:
    sub = subscriptions_collection.find_one({"user_id": user_id})
    if not sub:
        return "❌ Подписка не найдена для данного пользователя."
    status = sub.get("subscribed")
    start = sub.get("start_date")
    transaction_id = sub.get("transaction_id", "—")
    return (
        f"👤 ID: {user_id}\n"
        f"🟢 Статус: {status}\n"
        f"⏱ С: {start}\n"
        f"🔁 Транзакция: {transaction_id}"
    )

@router.message(lambda msg, t: msg.text == t["btn_subscription"])
async def payment_handler(message: Message, t: dict):
    user_id = message.from_user.id
    sub = subscriptions_collection.find_one({"user_id": user_id, "subscribed": True})

    if sub and sub.get("start_date"):
        start_date = sub["start_date"].date()
        end_date = start_date + timedelta(days=30)
        await message.answer(t["active_subscription_until"].format(date=end_date.strftime('%d %B %y')))
        return

    await message.answer_invoice(
        title="Plus Plan",
        description="Payment for a Plus Plan",
        payload="month_subscription",
        currency="XTR",
        prices=[LabeledPrice(label="XTR", amount=1)],
    )

@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout: PreCheckoutQuery):
    await pre_checkout.answer(ok=True)

@router.message(F.successful_payment)
async def successful_payment(message: Message, t: dict):
    add_subscription(message.from_user.id)
    charge_id = message.successful_payment.telegram_payment_charge_id
    subscriptions_collection.update_one(
        {"user_id": message.from_user.id},
        {"$set": {"transaction_id": charge_id}},
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

        start_date = sub.get("start_date")
        if start_date and (datetime.utcnow() - start_date) > timedelta(days=30):
            await message.answer(t["subscription_expired_no_refund"])
            return

        if charge_id != sub.get("transaction_id"):
            await message.answer(t["transaction_id_mismatch"])
            return

        await message.bot.refund_star_payment(
            user_id=user_id,
            telegram_payment_charge_id=charge_id
        )

        subscriptions_collection.update_one(
            {"user_id": user_id},
            {"$set": {"subscribed": False}}
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


def register(dp):
    dp.include_router(router)

@router.message(lambda msg, t: msg.text == t["btn_subscription"])
async def handle_subscription_button(message: Message, t: dict):
    await payment_handler(message, t)