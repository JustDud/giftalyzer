from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from bot_manager.states.marketsearch_states import MarketSearchState
from bot_manager.keyboards.search_keyboard import get_collection_keyboard, get_nft_keyboard, get_backdrop_keyboard
from mongo import collections_collection
from bot_manager.decorators.access import subscription_required

router = Router()


@router.callback_query(MarketSearchState.selecting_backdrop, F.data == "back_to_models")
async def handle_back_to_models(call: CallbackQuery, state: FSMContext, t: dict):
    await call.answer()
    data = await state.get_data()
    collection_name = data.get("selected_collection")
    selected_models = data.get("selected_models", [])
    page = data.get("current_nft_page", 0)

    collection = await collections_collection.find_one({"name": collection_name})
    if not collection:
        await call.answer(t["collection_not_found"])
        return
    collection_address = collection["address"]

    from mongo import nfts_collection
    nft_cursor = nfts_collection.find({"collection_address": collection_address}, {"model": 1})
    nfts = sorted({doc["model"] async for doc in nft_cursor if "model" in doc})

    from bot_manager.keyboards.search_keyboard import get_nft_keyboard
    keyboard = get_nft_keyboard(nfts, page=page, selected_models=selected_models, include_select_all=True, t=t)

    try:
        await call.message.edit_reply_markup(reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await state.set_state(MarketSearchState.selecting_gift)


@router.callback_query(F.data.startswith("next_page:"))
@router.callback_query(F.data.startswith("prev_page:"))
async def handle_pagination(call: CallbackQuery, state: FSMContext, t: dict):
    await call.answer()
    page = int(call.data.split(":")[1])
    collections_cursor = collections_collection.find({}, {"name": 1}).sort("name", 1)
    collections = [col["name"] async for col in collections_cursor if "name" in col]
    keyboard = get_collection_keyboard(collections, page=page, t=t)
    try:
        await call.message.edit_reply_markup(reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


@router.message(lambda msg, t: msg.text == t["btn_enter_manual"])
@subscription_required
async def handle_manual_input(message: Message, state: FSMContext, t: dict):
    collections_cursor = collections_collection.find({}, {"name": 1}).sort("name", 1)
    collections = [col["name"] async for col in collections_cursor if "name" in col]
    keyboard = get_collection_keyboard(collections, t=t)
    await message.answer(t["prompt_select_collection"], reply_markup=keyboard)
    await state.set_state(MarketSearchState.selecting_collection)


@router.callback_query(MarketSearchState.selecting_collection, lambda call, t: call.data.startswith("collection:"))
async def handle_collection_selection(call: CallbackQuery, state: FSMContext, t: dict):
    await call.answer()
    await state.update_data(cached_nfts=None, selected_models=[])
    collection_name = call.data.split(":", 1)[1]
    await state.update_data(selected_collection=collection_name)

    collection = await collections_collection.find_one({"name": collection_name})
    if not collection:
        await call.message.answer(t["collection_not_found"])
        return

    collection_address = collection["address"]
    from mongo import nfts_collection
    nft_cursor = nfts_collection.find({"collection_address": collection_address}, {"model": 1})
    nfts = sorted({doc["model"] async for doc in nft_cursor if "model" in doc})
    await state.update_data(cached_nfts=nfts)  # Кешируем модели

    keyboard = get_nft_keyboard(nfts, selected_models=[], include_select_all=True, t=t)

    await call.message.edit_text(t["prompt_select_model"].format(collection_name=collection_name))
    try:
        await call.message.edit_reply_markup(reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await state.set_state(MarketSearchState.selecting_gift)
    await state.update_data(current_nft_page=0)


@router.callback_query(
    MarketSearchState.selecting_gift,
    lambda call, t: call.data.startswith("nft_next_page:") or call.data.startswith("nft_prev_page:")
)
async def handle_nft_pagination(call: CallbackQuery, state: FSMContext, t: dict):
    await call.answer()
    print("NFT pagination triggered:", call.data)
    data = await state.get_data()
    collection_name = data.get("selected_collection")
    if not collection_name:
        await call.answer(t["collection_not_found"])
        return

    page = int(call.data.split(":")[1])
    nfts = data.get("cached_nfts", [])
    selected_models = data.get("selected_models", [])
    await state.update_data(current_nft_page=page)
    keyboard = get_nft_keyboard(nfts, page=page, selected_models=selected_models, include_select_all=True, t=t)

    try:
        await call.message.edit_reply_markup(reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


@router.callback_query(
    MarketSearchState.selecting_gift,
    lambda call, t: call.data.startswith("toggle_model:")
)
async def toggle_model_selection(call: CallbackQuery, state: FSMContext, t: dict):
    await call.answer()
    model = call.data.split(":", 1)[1]
    data = await state.get_data()
    selected_models = data.get("selected_models", [])
    if model in selected_models:
        selected_models.remove(model)
    else:
        selected_models.append(model)
    await state.update_data(
        selected_models=selected_models,
        cached_nfts=sorted(data.get("cached_nfts", [])),
        current_nft_page=data.get("current_nft_page", 0)
    )

    nfts = sorted(data.get("cached_nfts", []))
    from bot_manager.keyboards.search_keyboard import get_nft_keyboard
    page = data.get("current_nft_page", 0)
    keyboard = get_nft_keyboard(nfts, page=page, selected_models=selected_models, include_select_all=True, t=t)
    try:
        await call.message.edit_reply_markup(reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


@router.callback_query(MarketSearchState.selecting_gift, F.data == "select_all_models")
async def select_all_models(call: CallbackQuery, state: FSMContext, t: dict):
    await call.answer()
    data = await state.get_data()
    nfts = sorted(data.get("cached_nfts", []))
    await state.update_data(selected_models=nfts)
    from bot_manager.keyboards.search_keyboard import get_nft_keyboard
    page = data.get("current_nft_page", 0)
    keyboard = get_nft_keyboard(nfts, page=page, selected_models=nfts, include_select_all=True, t=t)
    try:
        await call.message.edit_reply_markup(reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


@router.callback_query(F.data == "back_to_main")
async def handle_back_to_main_menu(call: CallbackQuery, state: FSMContext, t: dict):
    await call.answer()
    await state.clear()
    await call.message.edit_text(t["returned_to_menu"])


@router.callback_query(F.data == "back_to_collections")
async def handle_back_to_collections(call: CallbackQuery, state: FSMContext, t: dict):
    await call.answer()
    collections_cursor = collections_collection.find({}, {"name": 1}).sort("name", 1)
    collections = [col["name"] async for col in collections_cursor if "name" in col]
    keyboard = get_collection_keyboard(collections, t=t)

    try:
        await call.message.edit_reply_markup(reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await state.set_state(MarketSearchState.selecting_collection)


@router.callback_query(MarketSearchState.selecting_gift, F.data == "proceed_to_backdrops")
async def handle_backdrop_selection(call: CallbackQuery, state: FSMContext, t: dict):
    data = await state.get_data()
    selected_models = data.get("selected_models", [])
    print(f"[DEBUG] Proceeding to backdrops with selected_models: {selected_models}")

    if not selected_models:
        print("[DEBUG] No models selected. Showing alert.")
        await call.answer("❌ " + t["select_one_model"], show_alert=True)
        return

    collection_name = data.get("selected_collection")

    collection = await collections_collection.find_one({"name": collection_name})
    if not collection:
        await call.answer(t["collection_not_found"])
        return
    collection_address = collection["address"]

    from mongo import nfts_collection
    nft_cursor = nfts_collection.find({
        "collection_address": collection_address,
        "model": {"$in": selected_models}
    }, {"backdrop": 1})
    backdrops = sorted({doc["backdrop"] async for doc in nft_cursor if "backdrop" in doc})

    if not backdrops:
        await call.answer(t["no_backdrops_available"], show_alert=True)
        await state.set_state(MarketSearchState.selecting_gift)
        return

    keyboard = get_backdrop_keyboard(backdrops, include_show_results_button=True, t=t)
    await state.update_data(cached_backdrops=backdrops, selected_backdrops=[])
    await call.message.edit_text(t["prompt_select_backdrop"].format(collection_name=collection_name))
    try:
        await call.message.edit_reply_markup(reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await state.set_state(MarketSearchState.selecting_backdrop)


@router.callback_query(MarketSearchState.selecting_backdrop, F.data == "select_all_backdrops")
async def select_all_backdrops(call: CallbackQuery, state: FSMContext, t: dict):
    await call.answer()
    data = await state.get_data()
    backdrops = sorted(data.get("cached_backdrops", []))

    await state.update_data(selected_backdrops=backdrops)
    await state.update_data(current_backdrop_page=0)

    from bot_manager.keyboards.search_keyboard import get_backdrop_keyboard
    keyboard = get_backdrop_keyboard(backdrops, selected_backdrops=backdrops, include_show_results_button=True, t=t)
    try:
        await call.message.edit_reply_markup(reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


@router.callback_query(
    MarketSearchState.selecting_backdrop,
    lambda call, t: call.data.startswith("backdrop:")
)
async def toggle_backdrop_selection(call: CallbackQuery, state: FSMContext, t: dict):
    await call.answer()
    backdrop = call.data.split(":", 1)[1]
    data = await state.get_data()
    selected_backdrops = data.get("selected_backdrops", [])
    if backdrop in selected_backdrops:
        selected_backdrops.remove(backdrop)
    else:
        selected_backdrops.append(backdrop)
    await state.update_data(selected_backdrops=selected_backdrops)

    from bot_manager.keyboards.search_keyboard import get_backdrop_keyboard
    keyboard = get_backdrop_keyboard(
        data.get("cached_backdrops", []),
        selected_backdrops,
        include_show_results_button=True,
        t=t
    )
    try:
        await call.message.edit_reply_markup(reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


@router.callback_query(MarketSearchState.selecting_backdrop, F.data == "show_filtered_results")
async def validate_and_proceed_to_results(call: CallbackQuery, state: FSMContext, t: dict):
    data = await state.get_data()
    selected_models = data.get("selected_models", [])
    selected_backdrops = data.get("selected_backdrops", [])

    if not selected_models and not selected_backdrops:
        await call.answer("❌ " + t["select_model_and_backdrop"], show_alert=True)
        return
    elif not selected_models:
        await call.answer("❌ " + t["select_one_model"], show_alert=True)
        return
    elif not selected_backdrops:
        try:
            await call.answer("❌ " + t["select_one_backdrop"], show_alert=True)
        except Exception as e:
            import logging
            logging.exception("Failed to send backdrop selection warning: %s", e)
        return

    await state.set_state(MarketSearchState.loading_results)
    from bot_manager.handlers.search_results import show_filtered_nfts
    await show_filtered_nfts(call, state, t)


def register(dp):
    dp.include_router(router)
