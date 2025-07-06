from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.exceptions import TelegramBadRequest

from bot_manager.keyboards.search_keyboard import get_collection_keyboard, get_nft_keyboard
from bot_manager.texts.ru import texts as t
from mongo import collections_collection


# FSM State class for market search
class MarketSearchState(StatesGroup):
    selecting_collection = State()
    selecting_gift = State()
    selecting_backdrop = State()

router = Router()


@router.callback_query(MarketSearchState.selecting_backdrop, F.data == "back_to_models")
async def handle_back_to_models(call: CallbackQuery, state: FSMContext):
    await call.answer()
    data = await state.get_data()
    collection_name = data.get("selected_collection")
    selected_models = data.get("selected_models", [])
    page = data.get("current_nft_page", 0)

    collection = collections_collection.find_one({"name": collection_name})
    if not collection:
        await call.answer("Коллекция не найдена.")
        return
    collection_address = collection["address"]

    from mongo import nfts_collection
    nft_cursor = nfts_collection.find({"collection_address": collection_address}, {"model": 1})
    nfts = list({doc["model"] for doc in nft_cursor if "model" in doc})

    from bot_manager.keyboards.search_keyboard import get_nft_keyboard
    keyboard = get_nft_keyboard(nfts, page=page, selected_models=selected_models, include_select_all=True)

    try:
        await call.message.edit_reply_markup(reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


@router.callback_query(F.data.startswith("next_page:"))
@router.callback_query(F.data.startswith("prev_page:"))
async def handle_pagination(call: CallbackQuery, state: FSMContext):
    await call.answer()
    page = int(call.data.split(":")[1])
    collections_cursor = collections_collection.find({}, {"name": 1})
    collections = [col["name"] for col in collections_cursor if "name" in col]
    keyboard = get_collection_keyboard(collections, page=page)
    try:
        await call.message.edit_reply_markup(reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise





@router.message(F.text == t["btn_enter_manual"])
async def handle_manual_input(message: Message, state: FSMContext):
    collections_cursor = collections_collection.find({}, {"name": 1})
    collections = [col["name"] for col in collections_cursor if "name" in col]
    keyboard = get_collection_keyboard(collections)
    await message.answer("Выберите коллекцию:", reply_markup=keyboard)
    await state.set_state(MarketSearchState.selecting_collection)


@router.callback_query(MarketSearchState.selecting_collection, F.data.startswith("collection:"))
async def handle_collection_selection(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.update_data(cached_nfts=None, selected_models=[])
    collection_name = call.data.split(":", 1)[1]
    await state.update_data(selected_collection=collection_name)

    collection = collections_collection.find_one({"name": collection_name})
    if not collection:
        await call.message.answer("Коллекция не найдена.")
        return

    collection_address = collection["address"]
    from mongo import nfts_collection
    nft_cursor = nfts_collection.find({"collection_address": collection_address}, {"model": 1})
    nfts = list({doc["model"] for doc in nft_cursor if "model" in doc})
    await state.update_data(cached_nfts=nfts)  # 💾 Кешируем модели

    keyboard = get_nft_keyboard(nfts, selected_models=[], include_select_all=True)

    await call.message.edit_text(f"Выберите модель из коллекции «{collection_name}»")
    try:
        await call.message.edit_reply_markup(reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await state.set_state(MarketSearchState.selecting_gift)
    await state.update_data(current_nft_page=0)


@router.callback_query(MarketSearchState.selecting_gift, F.data.startswith("nft_next_page:"))
@router.callback_query(MarketSearchState.selecting_gift, F.data.startswith("nft_prev_page:"))
async def handle_nft_pagination(call: CallbackQuery, state: FSMContext):
    await call.answer()
    print("NFT pagination triggered:", call.data)
    data = await state.get_data()
    collection_name = data.get("selected_collection")
    if not collection_name:
        await call.answer("Коллекция не выбрана.")
        return

    page = int(call.data.split(":")[1])
    nfts = data.get("cached_nfts", [])
    selected_models = data.get("selected_models", [])
    await state.update_data(current_nft_page=page)
    keyboard = get_nft_keyboard(nfts, page=page, selected_models=selected_models, include_select_all=True)

    try:
        await call.message.edit_reply_markup(reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


# Toggle model selection in NFT list
@router.callback_query(MarketSearchState.selecting_gift, F.data.startswith("toggle_model:"))
async def toggle_model_selection(call: CallbackQuery, state: FSMContext):
    await call.answer()
    model = call.data.split(":", 1)[1]
    data = await state.get_data()
    selected_models = data.get("selected_models", [])
    if model in selected_models:
        selected_models.remove(model)
    else:
        selected_models.append(model)
    await state.update_data(selected_models=selected_models)

    nfts = data.get("cached_nfts", [])
    from bot_manager.keyboards.search_keyboard import get_nft_keyboard
    page = data.get("current_nft_page", 0)
    keyboard = get_nft_keyboard(nfts, page=page, selected_models=selected_models, include_select_all=True)
    try:
        await call.message.edit_reply_markup(reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


# Select all models in NFT list
@router.callback_query(MarketSearchState.selecting_gift, F.data == "select_all_models")
async def select_all_models(call: CallbackQuery, state: FSMContext):
    await call.answer()
    data = await state.get_data()
    nfts = data.get("cached_nfts", [])
    await state.update_data(selected_models=nfts)
    from bot_manager.keyboards.search_keyboard import get_nft_keyboard
    page = data.get("current_nft_page", 0)
    keyboard = get_nft_keyboard(nfts, page=page, selected_models=nfts, include_select_all=True)
    try:
        await call.message.edit_reply_markup(reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise

@router.callback_query(F.data == "back_to_collections")
async def handle_back_to_collections(call: CallbackQuery, state: FSMContext):
    await call.answer()
    collections_cursor = collections_collection.find({}, {"name": 1})
    collections = [col["name"] for col in collections_cursor if "name" in col]
    keyboard = get_collection_keyboard(collections)

    try:
        await call.message.edit_reply_markup(reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await state.set_state(MarketSearchState.selecting_collection)


@router.callback_query(MarketSearchState.selecting_gift, F.data == "proceed_to_backdrops")
async def handle_backdrop_selection(call: CallbackQuery, state: FSMContext):
    await call.answer()
    data = await state.get_data()
    collection_name = data.get("selected_collection")
    selected_models = data.get("selected_models", [])

    if not selected_models:
        await call.answer("Пожалуйста, выберите хотя бы одну модель перед переходом к фонам.", show_alert=True)
        return

    collection = collections_collection.find_one({"name": collection_name})
    if not collection:
        await call.answer("Коллекция не найдена.")
        return
    collection_address = collection["address"]

    from mongo import nfts_collection
    nft_cursor = nfts_collection.find({
        "collection_address": collection_address,
        "model": {"$in": selected_models}
    }, {"backdrop": 1})
    backdrops = list({doc["backdrop"] for doc in nft_cursor if "backdrop" in doc})

    if not backdrops:
        await call.answer("Нет доступных фонов для выбранных моделей.", show_alert=True)
        await state.set_state(MarketSearchState.selecting_gift)
        return

    from bot_manager.keyboards.search_keyboard import get_backdrop_keyboard
    keyboard = get_backdrop_keyboard(backdrops, include_show_results_button=True)
    await state.update_data(cached_backdrops=backdrops, selected_backdrops=[])
    await call.message.edit_text(f"Выберите фон для коллекции «{collection_name}»")
    try:
        await call.message.edit_reply_markup(reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await state.set_state(MarketSearchState.selecting_backdrop)


@router.callback_query(MarketSearchState.selecting_backdrop, F.data == "select_all_backdrops")
async def select_all_backdrops(call: CallbackQuery, state: FSMContext):
    await call.answer()
    data = await state.get_data()
    backdrops = data.get("cached_backdrops", [])

    await state.update_data(selected_backdrops=backdrops)
    await state.update_data(current_backdrop_page=0)

    from bot_manager.keyboards.search_keyboard import get_backdrop_keyboard
    keyboard = get_backdrop_keyboard(backdrops, selected_backdrops=backdrops)
    try:
        await call.message.edit_reply_markup(reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


@router.callback_query(MarketSearchState.selecting_backdrop, F.data.startswith("backdrop:"))
async def toggle_backdrop_selection(call: CallbackQuery, state: FSMContext):
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
    keyboard = get_backdrop_keyboard(data.get("cached_backdrops", []), selected_backdrops)
    try:
        await call.message.edit_reply_markup(reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


def register(dp):
    dp.include_router(router)