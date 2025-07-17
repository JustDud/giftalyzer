from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_admin_keyboard(t):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t["btn_check_subscription"], callback_data="admin_check_subscription")],
        [InlineKeyboardButton(text=t["btn_refund"], callback_data="admin_refund")],
        [InlineKeyboardButton(text=t["btn_active_tickets"], callback_data="admin_show_active_tickets")],
        [InlineKeyboardButton(text=t["btn_close_all_tickets"], callback_data="admin_close_all_tickets")],
        [InlineKeyboardButton(text=t["btn_subscription_stats"], callback_data="admin_subscription_stats")],
        [InlineKeyboardButton(text=t["btn_manage_promocodes"], callback_data="admin_manage_promocodes")]
    ])


def get_promocodes_keyboard(t):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t["btn_add_promocode"], callback_data="admin_add_promocode")],
        [InlineKeyboardButton(text=t["btn_delete_promocode"], callback_data="admin_delete_promocode")],
        [InlineKeyboardButton(text=t["btn_list_promocodes"], callback_data="admin_list_promocodes")],
        [InlineKeyboardButton(text=t["btn_promocode_stats"], callback_data="admin_promocode_stats")],
        [InlineKeyboardButton(text=t["btn_top_promocodes"], callback_data="admin_top_promocodes")],
        [InlineKeyboardButton(text=t["btn_back_admin"], callback_data="admin_back_main")]
    ])