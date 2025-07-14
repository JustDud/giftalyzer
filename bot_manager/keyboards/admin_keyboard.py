from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_admin_keyboard(t):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t["btn_check_subscription"], callback_data="admin_check_subscription")],
        [InlineKeyboardButton(text=t["btn_refund"], callback_data="admin_refund")],
        [InlineKeyboardButton(text=t["btn_active_tickets"], callback_data="admin_show_active_tickets")],
        [InlineKeyboardButton(text=t["btn_close_all_tickets"], callback_data="admin_close_all_tickets")],
        [InlineKeyboardButton(text=t["btn_subscription_stats"], callback_data="admin_subscription_stats")]
    ])