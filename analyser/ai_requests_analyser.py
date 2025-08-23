from analyser.price_analyser import estimate_ton_price
from mongo import nfts_collection
import json
from bot_manager.keyboards.default import get_main_menu
from aiogram.exceptions import TelegramBadRequest
from analyser.forecaster import render_forecast, render_many
from mongo import collections_collection


async def analyse_ai_request(call, state, t, temp, gift_id=None):
    # msg refers to the main message object (Message or call.message)
    if hasattr(call, "message"):
        msg = call.message
    else:
        msg = call
    # Use gift_id if provided, otherwise use call.text, but only if call has .text
    if gift_id is not None:
        input_id = gift_id
    elif hasattr(call, "text"):
        input_id = call.text
    else:
        input_id = ""
    data = await state.get_data()
    user_question = data.get("user_question")
    selected_models = data.get("selected_models", [])
    selected_backdrops = data.get("selected_backdrops", [])
    selected_collection = data.get("selected_collection")

    # Fallback: extract model and backdrop from gift link if not already selected
    if not selected_models and gift_id:
        from analyser.page_parser import parse_telegram_gift_page
        parsed = await parse_telegram_gift_page(gift_id)
        if parsed:
            selected_models = [parsed["model"]]
            selected_backdrops = [parsed["backdrop"]]
            await state.update_data(selected_models=selected_models, selected_backdrops=selected_backdrops)
        else:
            await msg.answer("❌ Не удалось извлечь данные из ссылки.")
            try:
                await msg.answer(t["keyboard_restored"], reply_markup=get_main_menu(t))
            except Exception:
                await msg.answer(t["keyboard_restored"], reply_markup=get_main_menu(t))
            await state.clear()
            return

    # Get collection address by name or slug
    collection = None
    collection_slug = ""
    if selected_collection:
        collection = await collections_collection.find_one({"name": selected_collection})
    if not collection and gift_id:
        import re as _re
        collection_name = _re.sub(r'\d+', '', gift_id.split("-")[0])
        collection_slug = _re.sub(r'(?<!^)(?=[A-Z])', '-', collection_name).lower()
        collection = await collections_collection.find_one({"slug": collection_slug})
    if not collection:
        await msg.answer(f"❌ Коллекция '{selected_collection or collection_slug}' не найдена.")
        return

    collection_uid = collection["_id"]
    collection_slug = collection.get("slug", "")  # Assuming slug is stored in collection

    from itertools import product
    from mongo import find_nft_id_by_traits

    nft_details = []
    backdrop_combinations = selected_backdrops if selected_backdrops else [None]

    for model, backdrop in product(selected_models, backdrop_combinations):
        # Attempt to find nft_id by traits
        nft_id = await find_nft_id_by_traits(collection_slug, model, backdrop or "", "")
        if not nft_id:
            # If not found, skip this combination
            continue

        query = {
            "collection_uid": collection_uid,
            "markets": {"$exists": True},
            "traits": {
                "$all": [
                    {"$elemMatch": {"type": "model", "value": model}}
                ]
            }
        }
        if backdrop:
            query["traits"]["$all"].append({"$elemMatch": {"type": "backdrop", "value": backdrop}})

        async for nft in nfts_collection.find(query):
            traits = {t["type"]: t["value"] for t in nft.get("traits", [])}
            # Use nft_id found by traits instead of from DB _id
            # nft_id = nft.get("nft_id") or (nft.get("_id", "").split("#")[1] if "#" in nft.get("_id", "") else "")

            # Get collection-level volume
            volume_of_sales = int(float(collection.get("markets", {}).get("portals", {}).get("day_volume", {}).get("amount", 0)))

            rarity = None
            for trait in nft.get("traits", []):
                if trait.get("type") == "model" and "rarity_per_mille" in trait:
                    rarity = int(trait["rarity_per_mille"])
                    break

            nft_details.append({
                "id": nft_id,
                "name": nft_id.split("|")[-1].replace("-", " ").replace("#", " #").title(),
                "backdrop": traits.get("backdrop", backdrop or ""),
                "price": float(nft.get("markets", {}).get("portals", {}).get("price", {}).get("amount", 0)),
                "est_price": float(await estimate_ton_price(nft_id)) if nft_id else 0.0,
                "rarity": f"{rarity / 10:.1f}%" if rarity is not None else "—",
                "liquidity": int(float(collection.get("markets", {}).get("portals", {}).get("day_volume", {}).get("amount", 0)))
            })

    print(f"ANALYSIS DATA (detailed): {nft_details}")


    # Choose the system prompt
    if user_question == "🔍 Проанализируй NFT":
        if nft_details:
            try:
                ai_response = await render_forecast(nft_details[0])
                await state.update_data(ai_analysis=ai_response)
                from bot_manager.handlers.ai_requests_results import show_ai_analysis_results
                await show_ai_analysis_results(msg, state, t)
                return
            except Exception as e:
                import logging
                logging.exception("❌ Ошибка при генерации ответа: %s", e)
                await msg.answer("❌ Не удалось сгенерировать прогноз.")
        else:
            await msg.answer("❌ Не удалось найти подходящие NFT.")
        return
    elif user_question == "📈 Покажи недооцененные":
        system_prompt = "TEMPLATE: add undervalued NFT analysis prompt here"
    elif user_question == "⬆ Только с прогнозом 'up'":
        system_prompt = "TEMPLATE: add only-up forecast analysis prompt here"
    else:
        system_prompt = "TEMPLATE: default prompt"

    # Restore the main menu keyboard safely: clear inline keyboard if needed, then send confirmation with reply keyboard
    from aiogram.types import InlineKeyboardMarkup
    current_reply_markup = msg.reply_markup
    if current_reply_markup and getattr(current_reply_markup, "inline_keyboard", None):
        if current_reply_markup.inline_keyboard:
            try:
                try:
                    await msg.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=[]))
                except TelegramBadRequest as e:
                    if "message is not modified" not in str(e):
                        raise
            except Exception as e:
                import logging
                logging.warning(f"⚠️ Failed to edit reply markup: {e}")
        try:
            await msg.edit_reply_markup(reply_markup=get_main_menu(t))
        except Exception as e:
            await msg.answer(t["keyboard_restored"], reply_markup=get_main_menu(t))
    else:
        try:
            await msg.edit_reply_markup(reply_markup=get_main_menu(t))
        except Exception as e:
            await msg.answer(t["keyboard_restored"], reply_markup=get_main_menu(t))
    try:
        await temp.delete()
    except:
        pass
    await state.clear()
