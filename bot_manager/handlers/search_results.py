from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from mongo import collections_collection, nfts_collection
from analyser.price_analyser import estimate_ton_price, convert_ton_to_usd
from aiogram.exceptions import TelegramBadRequest

router = Router()

@router.callback_query(F.data == "show_filtered_results")
async def show_filtered_nfts(call: CallbackQuery, state: FSMContext):
    await call.answer()

    data = await state.get_data()
    selected_models = data.get("selected_models", [])
    selected_backdrops = data.get("selected_backdrops", [])

    if not selected_models and not selected_backdrops:
        await call.answer("❌ Выберите хотя бы одну модель и один фон.", show_alert=True)
        return
    elif not selected_models:
        await call.answer("❌ Выберите хотя бы одну модель.", show_alert=True)
        return
    elif not selected_backdrops:
        await call.answer("❌ Выберите хотя бы один фон.", show_alert=True)
        return

    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer("⏳ Подождите... Не закрывайте это окно.", show_alert=True)
    await call.message.edit_text("🔎 Подбор подарков по выбранным параметрам...")
    collection_name = data.get("selected_collection")

    collection = collections_collection.find_one({"name": collection_name})
    if not collection:
        await call.message.answer("Коллекция не найдена.")
        return

    collection_address = collection["address"]

    await call.message.edit_text("🔄 Обработка запроса, пожалуйста, подождите...")

    nft_cursor = nfts_collection.find({
        "collection_address": collection_address,
        "model": {"$in": selected_models},
        "backdrop": {"$in": selected_backdrops}
    })

    results = []
    for nft in nft_cursor:
        try:
            nft_id = nft.get("nft_id")
            ton_price = estimate_ton_price(nft_id) if nft_id else 0.0
        except Exception as e:
            print(f"[ERROR] Estimating price failed for NFT: {nft.get('name')}, reason: {e}")
            ton_price = 0.0

        try:
            market_price = float(nft.get("price", 0.0) or 0.0)
        except Exception:
            market_price = 0.0

        result = {
            "name": nft.get("name", "Unknown"),
            "model": nft.get("model", ""),
            "symbol": nft.get("symbol", ""),
            "background": nft.get("backdrop", ""),
            "ton": ton_price,
            "usd_estimated": convert_ton_to_usd(ton_price),
            "market": nft.get("market", "N/A"),
            "market_price": market_price,
            "usd_market": convert_ton_to_usd(market_price),
        }
        results.append(result)

    if not results:
        await call.message.edit_text("❌ Нет результатов по выбранным параметрам.")
        return

    from bot_manager.texts import ru as t
    text_blocks = [t.texts["gift_result"].format(**r) for r in results[:10]]
    full_text = "\n\n".join(text_blocks)
    await call.message.edit_text(full_text, reply_markup=None)



def register(dp):
    dp.include_router(router)