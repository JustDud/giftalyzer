from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from mongo import collections_collection, nfts_collection
from analyser.price_analyser import estimate_u_shape_by_id, convert_ton_to_usd
from aiogram.exceptions import TelegramBadRequest
import asyncio
from .market_search import MarketSearchState
from bot_manager.keyboards.default import get_main_menu

router = Router()


def get_pagination_keyboard(current_page: int, total_pages: int, t: dict):
    buttons = []
    if current_page > 0:
        buttons.append(InlineKeyboardButton(text=t["btn_prev_page"], callback_data="page_prev"))
    if current_page < total_pages - 1:
        buttons.append(InlineKeyboardButton(text=t["btn_next_page"], callback_data="page_next"))
    return InlineKeyboardMarkup(inline_keyboard=[buttons]) if buttons else None


@router.callback_query(F.data == "show_filtered_results")
async def show_filtered_nfts(call: CallbackQuery, state: FSMContext, t: dict):
    await call.answer()
    from aiogram.types import ReplyKeyboardRemove
    temp = await call.message.answer(t["locking_message"], reply_markup=ReplyKeyboardRemove())

    data = await state.get_data()
    selected_models = data.get("selected_models", [])
    selected_backdrops = data.get("selected_backdrops", [])
    await state.set_state(MarketSearchState.loading_results)

    from aiogram.types import ReplyKeyboardRemove
    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer(t["please_wait"], show_alert=True)
    interim_messages = t["loading_phrases"]
    await call.message.edit_text(interim_messages[0])
    collection_name = data.get("selected_collection")

    collection = await collections_collection.find_one({"name": collection_name})
    if not collection:
        await call.message.answer(t["collection_not_found"])
        return

    await call.message.edit_text(interim_messages[1])
    collection_uid = collection["_id"]
    nft_cursor = nfts_collection.find({
        "collection_uid": collection_uid,
        "traits": {
            "$all": [
                {"$elemMatch": {"type": "model", "value": {"$in": selected_models}}},
                {"$elemMatch": {"type": "backdrop", "value": {"$in": selected_backdrops}}}
            ]
        }
    }).limit(16)

    results = []
    async for nft in nft_cursor:
        try:
            nft_id = nft.get("_id")
            ton_price = await estimate_u_shape_by_id(nft_id) if nft_id else 0.0
        except Exception as e:
            print(f"[ERROR] Estimating price failed for NFT: {nft.get('name')}, reason: {e}")
            ton_price = 0.0

        try:
            market_price = float(nft.get("markets", {}).get("portals", {}).get("price", {}).get("amount", 0.0) or 0.0)
        except Exception:
            market_price = 0.0

        usd_estimated = await convert_ton_to_usd(ton_price)
        usd_market = await convert_ton_to_usd(market_price)

        result = {
            "name": nft.get("name", "Unknown"),
            "model": next((t["value"] for t in nft.get("traits", []) if t["type"] == "model"), ""),
            "symbol": next((t["value"] for t in nft.get("traits", []) if t["type"] == "symbol"), ""),
            "backdrop": next((t["value"] for t in nft.get("traits", []) if t["type"] == "backdrop"), ""),
            "ton": ton_price,
            "usd_estimated": usd_estimated,
            "market": "portals",
            "market_price": market_price,
            "usd_market": usd_market,
        }
        results.append(result)

        if len(results) % 15 == 0:
            progress_text = interim_messages[(len(results) // 15 - 1) % len(interim_messages)]
            try:
                if call.message.text != progress_text:
                    await call.message.edit_text(progress_text)
                    await asyncio.sleep(1)
            except TelegramBadRequest as e:
                if "message is not modified" not in str(e):
                    raise

    if not results:
        await call.message.edit_text(t["no_results_found"])
        return

    await temp.delete()
    await call.message.answer(t["keyboard_restored"], reply_markup=get_main_menu(t))

    await call.message.edit_text(interim_messages[2])
    await state.update_data(filtered_results=results, results_page=0)
    page = 0
    total_pages = (len(results) + 7) // 8
    chunk = results[page*8:(page+1)*8]
    text_blocks = [t["gift_result"].format(**r) for r in chunk]
    full_text = "\n\n-----------\n\n".join(text_blocks)

    reply_markup = get_pagination_keyboard(page, total_pages, t)
    await call.message.edit_text(t["processing_done"])
    await call.message.answer(full_text, reply_markup=reply_markup)


@router.callback_query(F.data.in_(["page_prev", "page_next"]))
async def paginate_filtered_results(call: CallbackQuery, state: FSMContext, t: dict):
    await call.answer()
    data = await state.get_data()
    results = data.get("filtered_results", [])
    page = data.get("results_page", 0)
    total_pages = (len(results) + 7) // 8

    if call.data == "page_next" and page < total_pages - 1:
        page += 1
    elif call.data == "page_prev" and page > 0:
        page -= 1

    chunk = results[page*8:(page+1)*8]
    text_blocks = [t["gift_result"].format(**r) for r in chunk]
    full_text = "\n\n-----------\n\n".join(text_blocks)

    reply_markup = get_pagination_keyboard(page, total_pages, t)
    try:
        await call.message.edit_text(full_text, reply_markup=reply_markup)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await state.update_data(results_page=page)


def register(dp):
    dp.include_router(router)
