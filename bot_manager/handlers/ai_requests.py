from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from bot_manager.states.ai_requests_state import AIRequestState, AIRequestCollectionAnalysisState
from bot_manager.keyboards.ai_requests_keyboard import (
    get_ai_collection_keyboard as get_collection_keyboard,
    get_ai_nft_keyboard as get_nft_keyboard,
    get_ai_backdrop_keyboard,
    get_ai_help_keyboard, get_analysis_method_keyboard
)
from mongo import collections_collection
from bot_manager.decorators.access import ai_access_required
from analyser.ai_requests_analyser import analyse_ai_request
from analyser.stars_collection import evaluate_gift
from mongo import nfts_collection
from aiogram.types import ReplyKeyboardRemove

router = Router()


@router.message(lambda msg, t: msg.text == t["btn_ask_ai"])
async def ai_help_start(message: Message, state: FSMContext, t):
    await state.update_data(user_question=message.text)
    await message.answer(t["ai_choose_action"], reply_markup=get_ai_help_keyboard(t))


@router.callback_query(F.data == "ai_analyse_gift")
@ai_access_required
async def handle_ai_analyse_gift(call: CallbackQuery, state: FSMContext, t: dict):
    await call.answer()
    await state.update_data(user_question=t["ai_analyse_gift"])
    await call.message.edit_text(t["choose_analysis_method"])
    await call.message.edit_reply_markup(reply_markup=get_analysis_method_keyboard(t))


@router.callback_query(F.data == "ai_analyse_collection")
@ai_access_required
async def handle_ai_analyse_collection(call: CallbackQuery, state: FSMContext, t: dict):
    await call.answer()
    await call.message.edit_text(t["ai_collection_analysis_intro"])
    await state.set_state(AIRequestCollectionAnalysisState.entering_supply)

# Handler for entering supply in collection analysis
@router.message(AIRequestCollectionAnalysisState.entering_supply)
async def handle_entering_supply(message: Message, state: FSMContext, t: dict):
    try:
        supply = int(message.text.strip())
    except ValueError:
        await message.answer(t["ai_error_invalid_supply"])
        return

    await state.update_data(supply=supply)
    await message.answer(t["ai_prompt_enter_price"])
    await state.set_state(AIRequestCollectionAnalysisState.entering_price)


# Handler for entering price and outputting results
@router.message(AIRequestCollectionAnalysisState.entering_price)
async def handle_entering_price(message: Message, state: FSMContext, t: dict):
    try:
        price = int(message.text.strip())
    except ValueError:
        await message.answer(t["ai_error_invalid_price"])
        return

    data = await state.get_data()
    supply = data.get("supply")

    result = evaluate_gift(supply, price)
    await message.answer(t["ai_analysis_collection_result_template"].format(**result))
    await state.clear()



# Handler for manual analysis entry (choose collection manually)
@router.callback_query(F.data == "ai_analysis_manual")
async def handle_manual_analysis_entry(call: CallbackQuery, state: FSMContext, t: dict):
    await call.answer()
    collections_cursor = collections_collection.find({}, {"name": 1}).sort("name", 1)
    collections = [col["name"] async for col in collections_cursor if "name" in col]
    keyboard = get_collection_keyboard(collections, t=t)
    await call.message.edit_text(t["prompt_select_collection"])
    await call.message.edit_reply_markup(reply_markup=keyboard)
    await state.set_state(AIRequestState.selecting_collection)


# Handler for analysis by link
@router.callback_query(F.data == "ai_analysis_by_link")
async def handle_link_analysis_entry(call: CallbackQuery, state: FSMContext, t: dict):
    await call.answer()
    await call.message.edit_text(t["id_input_prompt"])
    if call.message.reply_markup:
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                raise
    await state.set_state(AIRequestState.entering_link)


# Handler for processing the link input from user
@router.message(AIRequestState.entering_link)
async def process_link_input(message: Message, state: FSMContext, t: dict):
    gift_id = message.text.strip()
    if "/nft/" in gift_id:
        gift_id = gift_id.split("/nft/")[-1]
    elif "/" in gift_id:
        gift_id = gift_id.rsplit("/", 1)[-1]
    gift_id = gift_id.strip().strip("/")

    temp = await message.answer(t["locking_message"], reply_markup=ReplyKeyboardRemove())
    await message.answer("⌛ Генерация анализа, пожалуйста подождите...")
    await state.set_state(AIRequestState.loading_results)

    # Try to resolve and display NFT image before running analysis
    try:
        doc = await nfts_collection.find_one(
            {
                "$or": [
                    {"_id": gift_id},
                    {"external_ids.portals.id": gift_id},
                    {"token_id": gift_id},
                ]
            },
            {"media": 1, "name": 1}
        )
        if doc:
            image_url = (doc.get("media") or {}).get("image_url")
            if image_url:
                await message.answer_photo(photo=image_url, caption=doc.get("name", ""))
    except Exception as e:
        print(f"[ai_requests] failed to pre-send NFT image: {e!r}")

    await analyse_ai_request(message, state, t, temp, gift_id=gift_id)


@router.callback_query(AIRequestState.selecting_backdrop, F.data == "ai_back_to_models")
async def handle_back_to_models(call: CallbackQuery, state: FSMContext, t: dict):
    await call.answer()
    data = await state.get_data()
    collection_name = data.get("selected_collection")
    selected_models = data.get("selected_models", [])
    page = data.get("current_nft_page", 0)

    collection = await collections_collection.find_one({"name": collection_name})
    if not collection:
        await call.answer(t["ai_collection_not_found"])
        return
    collection_uid = collection["_id"]

    nft_cursor = nfts_collection.find({
        "collection_uid": collection_uid,
        "$or": [
            {"market_data": {"$exists": True, "$nin": [None, [], {}]}},
            {"markets": {"$exists": True, "$nin": [None, [], {}]}},
            {"listings": {"$exists": True, "$nin": [None, [], {}]}}
        ]
    }, {"traits": 1})
    models = set()
    async for doc in nft_cursor:
        for trait in doc.get("traits", []):
            if trait.get("type") == "model":
                models.add(trait.get("value"))
    nfts = sorted(models)

    keyboard = get_nft_keyboard(nfts, page=page, selected_models=selected_models, include_select_all=True, t=t)

    await call.message.edit_text(t["ai_prompt_select_model"].format(collection_name=collection_name))
    try:
        await call.message.edit_reply_markup(reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await state.set_state(AIRequestState.selecting_gift)


@router.callback_query(F.data.startswith("ai_next_page:"))
@router.callback_query(F.data.startswith("ai_prev_page:"))
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
async def handle_manual_input(message: Message, state: FSMContext, t: dict):
    collections_cursor = collections_collection.find({}, {"name": 1}).sort("name", 1)
    collections = [col["name"] async for col in collections_cursor if "name" in col]
    keyboard = get_collection_keyboard(collections, t=t)
    await message.answer(t["prompt_select_collection"], reply_markup=keyboard)
    await state.set_state(AIRequestState.selecting_collection)


@router.callback_query(AIRequestState.selecting_collection)
async def handle_collection_selection(call: CallbackQuery, state: FSMContext, t: dict):
    import re
    # Exit early if user pressed "Back to main"
    if call.data == "ai_back_to_analysis_method":
        await handle_ai_back_to_analysis_method(call, state, t)
        return
    # If user pasted a link directly instead of pressing a button
    if not call.data.startswith("ai_collection:"):
        # Extract potential gift ID from link
        gift_id = call.data.strip()
        if "/nft/" in gift_id:
            gift_id = gift_id.split("/nft/")[-1]
        elif "/" in gift_id:
            gift_id = gift_id.rsplit("/", 1)[-1]
        gift_id = gift_id.strip().strip("/")

        await call.answer()
        temp = await call.message.answer(t["locking_message"], reply_markup=ReplyKeyboardRemove())
        await call.message.edit_reply_markup(reply_markup=None)
        await call.message.edit_text("⌛ Генерация анализа, пожалуйста подождите...", reply_markup=None)
        await state.set_state(AIRequestState.loading_results)

        # Instead of assigning .text (which is not allowed/frozen), pass gift_id as an argument
        await analyse_ai_request(call, state, t, temp, gift_id=gift_id)
        return

    await call.answer()
    await state.update_data(cached_nfts=None, selected_models=[])
    collection_name = call.data.split(":", 1)[1]
    await state.update_data(selected_collection=collection_name)

    collection = await collections_collection.find_one({"name": collection_name})
    if not collection:
        await call.message.answer(t["ai_collection_not_found"])
        return

    collection_uid = collection["_id"]
    nft_cursor = nfts_collection.find({
        "collection_uid": collection_uid,
        "$or": [
            {"market_data": {"$exists": True, "$nin": [None, [], {}]}},
            {"markets": {"$exists": True, "$nin": [None, [], {}]}},
            {"listings": {"$exists": True, "$nin": [None, [], {}]}}
        ]
    }, {"traits": 1})
    models = set()
    async for doc in nft_cursor:
        for trait in doc.get("traits", []):
            if trait.get("type") == "model":
                models.add(trait.get("value"))
    nfts = sorted(models)
    await state.update_data(cached_nfts=nfts)  # Кешируем модели

    keyboard = get_nft_keyboard(nfts, selected_models=[], include_select_all=True, t=t)

    await call.message.edit_text(t["ai_prompt_select_model"].format(collection_name=collection_name))
    try:
        await call.message.edit_reply_markup(reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await state.set_state(AIRequestState.selecting_gift)
    await state.update_data(current_nft_page=0)


@router.callback_query(
    AIRequestState.selecting_gift,
    lambda call, t: call.data.startswith("ai_nft_next_page:") or call.data.startswith("ai_nft_prev_page:")
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
    AIRequestState.selecting_gift,
    lambda call, t: call.data.startswith("ai_toggle_model:")
)
async def toggle_model_selection(call: CallbackQuery, state: FSMContext, t: dict):
    await call.answer()
    model = call.data.split(":", 1)[1]
    await state.update_data(selected_models=[model])
    print(f"[DEBUG] Single model selected: {model}")

    # Immediately proceed to backdrops
    data = await state.get_data()
    collection_name = data.get("selected_collection")

    collection = await collections_collection.find_one({"name": collection_name})
    if not collection:
        await call.answer(t["ai_collection_not_found"])
        return

    collection_uid = collection["_id"]
    nft_cursor = nfts_collection.find({
        "collection_uid": collection_uid,
        "traits": {"$elemMatch": {"type": "model", "value": model}},
        "$or": [
            {"market_data": {"$exists": True, "$nin": [None, [], {}]}},
            {"markets": {"$exists": True, "$nin": [None, [], {}]}},
            {"listings": {"$exists": True, "$nin": [None, [], {}]}}
        ]
    }, {"traits": 1})
    backdrops = set()
    async for doc in nft_cursor:
        for trait in doc.get("traits", []):
            if trait.get("type") == "backdrop":
                backdrops.add(trait.get("value"))
    backdrops = sorted(backdrops)

    if not backdrops:
        await call.answer(t["ai_no_backdrops_available"], show_alert=True)
        await state.set_state(AIRequestState.selecting_gift)
        return

    keyboard = get_ai_backdrop_keyboard(backdrops, t=t, selection_limit=1)
    await state.update_data(cached_backdrops=backdrops, selected_backdrops=[])
    await state.update_data(backdrop_selection_limit=1)
    await call.message.edit_text(t["ai_prompt_select_backdrop"].format(collection_name=collection_name))
    try:
        await call.message.edit_reply_markup(reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await state.set_state(AIRequestState.selecting_backdrop)


@router.callback_query(AIRequestState.selecting_gift, F.data == "ai_select_all_models")
async def select_all_models(call: CallbackQuery, state: FSMContext, t: dict):
    await call.answer()
    data = await state.get_data()
    nfts = sorted(data.get("cached_nfts", []))
    await state.update_data(selected_models=nfts)
    page = data.get("current_nft_page", 0)
    keyboard = get_nft_keyboard(nfts, page=page, selected_models=nfts, include_select_all=True, t=t)
    try:
        await call.message.edit_reply_markup(reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


@router.callback_query(F.data == "ai_back_to_main")
async def handle_back_to_ai_help(call: CallbackQuery, state: FSMContext, t: dict):
    await call.answer()
    await state.clear()

    keyboard = get_ai_help_keyboard(t)
    await call.message.edit_text(t["returned_to_menu"])
    await call.message.edit_reply_markup(reply_markup=keyboard)

@router.callback_query(F.data == "ai_back_to_analysis_method")
async def handle_ai_back_to_analysis_method(call: CallbackQuery, state: FSMContext, t: dict):
    await call.answer()
    await state.clear()

    keyboard = get_analysis_method_keyboard(t)
    # await call.message.edit_text(t["returned_to_menu"])
    await call.message.edit_reply_markup(reply_markup=keyboard)


@router.callback_query(F.data == "ai_back_to_collections")
async def handle_back_to_collections(call: CallbackQuery, state: FSMContext, t: dict):
    await call.answer()
    collections_cursor = collections_collection.find({}, {"name": 1}).sort("name", 1)
    collections = [col["name"] async for col in collections_cursor if "name" in col]
    keyboard = get_collection_keyboard(collections, t=t)

    await call.message.edit_text(t["ai_prompt_select_collection"])
    try:
        await call.message.edit_reply_markup(reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await state.set_state(AIRequestState.selecting_collection)


@router.callback_query(AIRequestState.selecting_gift, F.data == "ai_proceed_to_backdrops")
async def handle_backdrop_selection(call: CallbackQuery, state: FSMContext, t: dict):
    data = await state.get_data()
    selected_models = data.get("selected_models", [])
    print(f"[DEBUG] Proceeding to backdrops with selected_models: {selected_models}")

    if not selected_models:
        print("[DEBUG] No models selected. Showing alert.")
        await call.answer("❌ " + t["ai_select_one_model"], show_alert=True)
        return

    collection_name = data.get("selected_collection")

    collection = await collections_collection.find_one({"name": collection_name})
    if not collection:
        await call.answer(t["ai_collection_not_found"])
        return
    collection_uid = collection["_id"]

    nft_cursor = nfts_collection.find({
        "collection_uid": collection_uid,
        "traits": {"$elemMatch": {"type": "model", "value": {"$in": selected_models}}},
        "$or": [
            {"market_data": {"$exists": True, "$nin": [None, [], {}]}},
            {"markets": {"$exists": True, "$nin": [None, [], {}]}},
            {"listings": {"$exists": True, "$nin": [None, [], {}]}}
        ]
    }, {"traits": 1})
    backdrops = set()
    async for doc in nft_cursor:
        for trait in doc.get("traits", []):
            if trait.get("type") == "backdrop":
                backdrops.add(trait.get("value"))
    backdrops = sorted(backdrops)

    if not backdrops:
        await call.answer(t["ai_no_backdrops_available"], show_alert=True)
        await state.set_state(AIRequestState.selecting_gift)
        return

    keyboard = get_ai_backdrop_keyboard(backdrops, t=t, selection_limit=3)
    await state.update_data(cached_backdrops=backdrops, selected_backdrops=[])
    await state.update_data(backdrop_selection_limit=3)
    await call.message.edit_text(t["ai_prompt_select_backdrop"].format(collection_name=collection_name))
    try:
        await call.message.edit_reply_markup(reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await state.set_state(AIRequestState.selecting_backdrop)


@router.callback_query(AIRequestState.selecting_backdrop, F.data == "ai_select_all_backdrops")
async def select_all_backdrops(call: CallbackQuery, state: FSMContext, t: dict):
    await call.answer()
    data = await state.get_data()
    backdrops = sorted(data.get("cached_backdrops", []))

    await state.update_data(selected_backdrops=backdrops)
    await state.update_data(current_backdrop_page=0)

    keyboard = get_ai_backdrop_keyboard(backdrops, selected_backdrops=backdrops, t=t, selection_limit=3)
    try:
        await call.message.edit_reply_markup(reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


@router.callback_query(
    AIRequestState.selecting_backdrop,
    lambda call, t: call.data.startswith("ai_backdrop:")
)
async def toggle_backdrop_selection(call: CallbackQuery, state: FSMContext, t: dict):
    await call.answer()  # Always acknowledge first to avoid "not handled"
    backdrop = call.data.split(":", 1)[1]
    data = await state.get_data()
    selected_backdrops = data.get("selected_backdrops", [])
    limit = data.get("backdrop_selection_limit", 3)  # Default to 3 if not set

    if backdrop in selected_backdrops:
        selected_backdrops.remove(backdrop)
    else:
        if limit == 0 or len(selected_backdrops) < limit:
            selected_backdrops.append(backdrop)
        else:
            await call.answer(f"❌ Можно выбрать максимум {limit} фонов.", show_alert=True)
            return

    await state.update_data(selected_backdrops=selected_backdrops)

    keyboard = get_ai_backdrop_keyboard(
        data.get("cached_backdrops", []),
        selected_backdrops,
        t=t,
        selection_limit=limit
    )
    try:
        await call.message.edit_reply_markup(reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


@router.callback_query(AIRequestState.selecting_backdrop, F.data == "ai_show_results")
@ai_access_required
async def validate_and_proceed_to_ai(call: CallbackQuery, state: FSMContext, t: dict):
    data = await state.get_data()
    selected_backdrops = data.get("selected_backdrops", [])

    if not selected_backdrops:
        try:
            await call.answer("❌ " + t["ai_select_backdrop"], show_alert=True)
        except Exception as e:
            import logging
            logging.exception("Failed to send backdrop selection warning: %s", e)
        return

    await call.answer()
    temp = await call.message.answer(t["locking_message"], reply_markup=ReplyKeyboardRemove())
    # Remove inline keyboard safely before editing text
    current_reply_markup = call.message.reply_markup
    if current_reply_markup is not None:
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                raise
    try:
        await call.message.edit_text("⌛ Генерация анализа, пожалуйста подождите...", reply_markup=None)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await state.set_state(AIRequestState.loading_results)
    await analyse_ai_request(call, state, t, temp)


def register(dp):
    dp.include_router(router)
