from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot_manager.texts.ru import texts as t


def get_nft_keyboard(
    nfts: list[str],
    page: int = 0,
    per_page: int = 30,
    selected_models: list[str] = None,
    include_select_all: bool = False,
    next_label: str = t["btn_next_page"],
    prev_label: str = t["btn_prev_page"]
) -> InlineKeyboardMarkup:
    selected_models = selected_models or []
    start = page * per_page
    end = start + per_page

    rows = [
        [
            InlineKeyboardButton(
                text=("✅ " if nfts[start:end][i] in selected_models else "") + nfts[start:end][i],
                callback_data=f"toggle_model:{nfts[start:end][i]}"
            )
            for i in range(j, min(j + 3, len(nfts[start:end])))
        ]
        for j in range(0, len(nfts[start:end]), 3)
    ]

    if include_select_all:
        rows.append([
            InlineKeyboardButton(text=t["btn_select_all_models"], callback_data="select_all_models")
        ])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text=prev_label, callback_data=f"nft_prev_page:{page - 1}"))
    if end < len(nfts):
        nav_buttons.append(InlineKeyboardButton(text=next_label, callback_data=f"nft_next_page:{page + 1}"))

    if nav_buttons:
        rows.append(nav_buttons)

    rows.append([
        InlineKeyboardButton(text=t["btn_proceed_to_backdrops"], callback_data="proceed_to_backdrops")
    ])

    rows.append([InlineKeyboardButton(text=t["btn_back_to_collections"], callback_data="back_to_collections")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_collection_keyboard(collections: list[str], page: int = 0, per_page: int = 30, next_label: str = t["btn_next_page"], prev_label: str = t["btn_prev_page"]) -> InlineKeyboardMarkup:
    start = page * per_page
    end = start + per_page

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=collections[start:end][i], callback_data=f"collection:{collections[start:end][i]}")
            for i in range(j, min(j + 3, len(collections[start:end])))
        ]
        for j in range(0, len(collections[start:end]), 3)
    ])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text=prev_label, callback_data=f"prev_page:{page - 1}"))
    if end < len(collections):
        nav_buttons.append(InlineKeyboardButton(text=next_label, callback_data=f"next_page:{page + 1}"))

    if nav_buttons:
        keyboard.inline_keyboard.append(nav_buttons)

    keyboard.inline_keyboard.append([InlineKeyboardButton(text=t["btn_back_to_main"], callback_data="back_to_main")])
    return keyboard


def get_backdrop_keyboard(
    backdrops: list[str],
    selected_backdrops: list[str] = None,
    include_show_results_button: bool = False
) -> InlineKeyboardMarkup:
    selected_backdrops = selected_backdrops or []
    rows = [
        [
            InlineKeyboardButton(
                text=("✅ " if backdrops[i] in selected_backdrops else "") + backdrops[i],
                callback_data=f"backdrop:{backdrops[i]}"
            )
            for i in range(j, min(j + 3, len(backdrops)))
        ]
        for j in range(0, len(backdrops), 3)
    ]

    rows.append([
        InlineKeyboardButton(text=t["btn_select_all_backdrops"], callback_data="select_all_backdrops")
    ])

    if include_show_results_button:
        rows.append([InlineKeyboardButton(text=t["btn_show_filtered_results"], callback_data="show_filtered_results")])

    rows.append([
        InlineKeyboardButton(text=t["btn_back_to_models"], callback_data="back_to_models")
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)
