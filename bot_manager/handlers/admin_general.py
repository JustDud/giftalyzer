from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from bot_manager.keyboards.admin_keyboard import admin_keyboard

router = Router()

@router.message(Command("admin_panel"))
async def admin_panel(message: Message):
    # Убедись, что это в группе и от админа
    if message.chat.type not in ["group", "supergroup"]:
        return
    admins = await message.bot.get_chat_administrators(message.chat.id)
    admin_ids = [admin.user.id for admin in admins]

    if message.from_user.id not in admin_ids:
        await message.answer("❌ У вас нет доступа к админ-панели.")
        return

    await message.answer("🛠 Админ-панель активирована.", reply_markup=admin_keyboard)


# Обработчик для кнопки "🔄 Проверить подписку"
@router.message(F.text == "🔄 Проверить подписку")
async def admin_check_subscription(message: Message):
    await message.answer("🔍 Введите <b>User ID</b> для проверки подписки:", parse_mode="HTML")

# Обработчик для кнопки "💸 Рефанд"
@router.message(F.text == "💸 Рефанд")
async def admin_refund_info(message: Message):
    await message.answer("Введите команду: /refund <user_id> <transaction_id>")

def register(dp):
    dp.include_router(router)