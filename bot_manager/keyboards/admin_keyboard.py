from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔄 Проверить подписку", callback_data="admin_check_subscription")],
    [InlineKeyboardButton(text="💸 Рефанд", callback_data="admin_refund")],
    [InlineKeyboardButton(text="📬 Активные тикеты", callback_data="admin_show_active_tickets")],
    [InlineKeyboardButton(text="✅ Закрыть все тикеты", callback_data="admin_close_all_tickets")],
    [InlineKeyboardButton(text="📊 Статистика подписок", callback_data="admin_subscription_stats")]
])