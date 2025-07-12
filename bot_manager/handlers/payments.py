from aiogram.types import Message
from aiogram import Router, F
from aiogram.types import Message, LabeledPrice, PreCheckoutQuery
from subscription.manager import add_subscription
from mongo import get_all_subscriptions
from mongo import subscriptions_collection
from datetime import datetime, timedelta
import os
from bot_manager.texts.ru import texts as t

admin_ids = os.getenv("ADMIN_IDS", "")
admin_ids = [int(id.strip()) for id in admin_ids.split(",") if id.strip()]

router = Router()


@router.message(F.text == t["btn_subscription"])
async def payment_handler(message: Message):
    user_id = message.from_user.id
    sub = subscriptions_collection.find_one({"user_id": user_id, "subscribed": True})

    if sub and sub.get("start_date"):
        start_date = sub["start_date"].date()
        end_date = start_date + timedelta(days=30)
        await message.answer(f"🔔 У вас уже есть активная подписка до {end_date.strftime('%Y-%m-%d')}.")
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
async def successful_payment(message: Message):
    add_subscription(message.from_user.id)
    charge_id = message.successful_payment.telegram_payment_charge_id
    subscriptions_collection.update_one(
        {"user_id": message.from_user.id},
        {"$set": {"transaction_id": charge_id}},
        upsert=True
    )
    await message.answer(
        f"✅ Подписка активирована на 30 дней. Спасибо за оплату!\n🔁 Transaction ID: \n{charge_id}"
    )

@router.message(F.text.startswith("/check_subs"))
async def check_subscriptions(message: Message):
    if message.from_user.id not in admin_ids:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    try:
        parts = message.text.split()
        if len(parts) == 2:
            try:
                user_id = int(parts[1])
            except ValueError:
                await message.answer("⚠️ Неверный формат ID пользователя.")
                return
            sub = subscriptions_collection.find_one({"user_id": user_id})
            if not sub:
                await message.answer("❌ Подписка не найдена для данного пользователя.")
                return
            status = sub.get("subscribed")
            start = sub.get("start_date")
            transaction_id = sub.get("transaction_id", "—")
            await message.answer(
                f"👤 ID: {user_id}\n🟢 Статус: {status}\n⏱ С: {start}\n🔁 Транзакция: {transaction_id}"
            )
        else:
            subs = get_all_subscriptions()
            if not subs:
                await message.answer("📭 Подписок не найдено.")
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
        await message.answer(f"❌ Ошибка при проверке подписок: {e}")



# Admin-only refund command: /refund <user_id> <charge_id>
@router.message(F.text.startswith("/refund"))
async def admin_refund_handler(message: Message):
    if message.from_user.id not in admin_ids:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("⚠️ Использование: /refund <user_id> <charge_id>")
        return

    try:
        user_id = int(parts[1])
        charge_id = parts[2]

        sub = subscriptions_collection.find_one({"user_id": user_id})
        if not sub or not sub.get("subscribed"):
            await message.answer("❌ У пользователя нет активной подписки.")
            return

        start_date = sub.get("start_date")
        if start_date and (datetime.utcnow() - start_date) > timedelta(days=30):
            await message.answer("⚠️ Подписка уже истекла, возврат невозможен.")
            return

        if charge_id != sub.get("transaction_id"):
            await message.answer("⚠️ Этот ID транзакции не соответствует последней активной подписке пользователя.")
            return

        await message.bot.refund_star_payment(
            user_id=user_id,
            telegram_payment_charge_id=charge_id
        )

        subscriptions_collection.update_one(
            {"user_id": user_id},
            {"$set": {"subscribed": False}}
        )

        await message.answer(f"✅ Подписка пользователя {user_id} отключена, возврат выполнен.")
    except Exception as e:
        await message.answer(f"❌ Ошибка при возврате: {e}")


def register(dp):
    dp.include_router(router)

@router.message(F.text == "🌟 Подписка")
async def handle_subscription_button(message: Message):
    await payment_handler(message)