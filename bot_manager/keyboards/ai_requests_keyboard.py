from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_ai_help_keyboard(t):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t["ai_analyse_gift"], callback_data="ai_analyze_gift")],
            [InlineKeyboardButton(text=t["ai_undervalued"], callback_data="ai_undervalued")],
            [InlineKeyboardButton(text=t["ai_only_up"], callback_data="ai_only_up")],
    ])



def get_ai_nft_keyboard(
    nfts: list[str],
    page: int = 0,
    per_page: int = 30,
    selected_models: list[str] = None,
    include_select_all: bool = False,
    next_label: str = None,
    prev_label: str = None,
    t: dict = None,
    selection_limit: int = 3
) -> InlineKeyboardMarkup:
    selected_models = selected_models or []
    start = page * per_page
    end = start + per_page

    next_label = next_label or t["btn_next_page"]
    prev_label = prev_label or t["btn_prev_page"]

    rows = []
    for j in range(0, len(nfts[start:end]), 3):
        row = []
        for i in range(j, min(j + 3, len(nfts[start:end]))):
            item = nfts[start:end][i]
            is_selected = item in selected_models
            is_disabled = selection_limit > 0 and not is_selected and len(selected_models) >= selection_limit
            text = ("✅ " if is_selected else "") + item
            callback = f"ai_toggle_model:{item}" if not is_disabled else "ignore"
            row.append(InlineKeyboardButton(text=text, callback_data=callback))
        rows.append(row)


    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text=prev_label, callback_data=f"ai_nft_prev_page:{page - 1}"))
    if end < len(nfts):
        nav_buttons.append(InlineKeyboardButton(text=next_label, callback_data=f"ai_nft_next_page:{page + 1}"))

    if nav_buttons:
        rows.append(nav_buttons)


    rows.append([InlineKeyboardButton(text=t["btn_back_to_collections"], callback_data="ai_back_to_collections")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_ai_collection_keyboard(
    collections: list[str],
    page: int = 0,
    per_page: int = 30,
    next_label: str = None,
    prev_label: str = None,
    t: dict = None
) -> InlineKeyboardMarkup:
    start = page * per_page
    end = start + per_page

    next_label = next_label or t["btn_next_page"]
    prev_label = prev_label or t["btn_prev_page"]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=collections[start:end][i], callback_data=f"ai_collection:{collections[start:end][i]}")
            for i in range(j, min(j + 3, len(collections[start:end])))
        ]
        for j in range(0, len(collections[start:end]), 3)
    ])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text=prev_label, callback_data=f"ai_prev_page:{page - 1}"))
    if end < len(collections):
        nav_buttons.append(InlineKeyboardButton(text=next_label, callback_data=f"ai_next_page:{page + 1}"))

    if nav_buttons:
        keyboard.inline_keyboard.append(nav_buttons)

    keyboard.inline_keyboard.append([InlineKeyboardButton(text=t["btn_back_to_main"], callback_data="ai_back_to_main")])
    return keyboard


def get_ai_backdrop_keyboard(
    backdrops: list[str],
    selected_backdrops: list[str] = None,
    t: dict = None,
    selection_limit: int = 3
) -> InlineKeyboardMarkup:
    selected_backdrops = selected_backdrops or []

    rows = []
    for j in range(0, len(backdrops), 3):
        row = []
        for i in range(j, min(j + 3, len(backdrops))):
            item = backdrops[i]
            is_selected = item in selected_backdrops
            is_disabled = selection_limit > 0 and not is_selected and len(selected_backdrops) >= selection_limit
            text = ("✅ " if is_selected else "") + item
            callback = f"ai_backdrop:{item}" if not is_disabled else "ignore"
            row.append(InlineKeyboardButton(text=text, callback_data=callback))
        rows.append(row)

    rows.append([InlineKeyboardButton(text=t["btn_show_filtered_results"], callback_data="ai_show_results")])
    rows.append([InlineKeyboardButton(text=t["btn_back_to_models"], callback_data="ai_back_to_models")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_analysis_method_keyboard(t: dict) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text=t["btn_link_analysis"], callback_data="ai_analysis_by_link")],
        [InlineKeyboardButton(text=t["btn_manual_analysis"], callback_data="ai_analysis_manual")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
