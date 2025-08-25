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
    link_input = input_id  # ссылка/ID может прийти как gift_id или как текст сообщения
    data = await state.get_data()
    user_question = data.get("user_question")
    user_question_key = data.get("user_question_key")
    selected_models = data.get("selected_models", [])
    selected_backdrops = data.get("selected_backdrops", [])
    selected_collection = data.get("selected_collection")

    # Fallback: extract model and backdrop from gift link if not already selected
    if not selected_models and link_input:
        from analyser.page_parser import parse_telegram_gift_page
        parsed = await parse_telegram_gift_page(link_input)
        if parsed:
            selected_models = [parsed["model"]]
            selected_backdrops = [parsed["backdrop"]]
            selected_symbol = parsed.get("symbol")
            await state.update_data(
                selected_models=selected_models,
                selected_backdrops=selected_backdrops,
                selected_symbol=selected_symbol,
            )
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
    if not collection and link_input:
        import re as _re
        collection_name = _re.sub(r'\d+', '', link_input.split("-")[0])
        collection_slug = _re.sub(r'(?<!^)(?=[A-Z])', '-', collection_name).lower()
        collection = await collections_collection.find_one({"slug": collection_slug})
    if not collection:
        await msg.answer(f"❌ Коллекция '{selected_collection or collection_slug}' не найдена.")
        return

    collection_uid = collection["_id"]
    collection_slug = collection.get("slug", "")  # Assuming slug is stored in collection

    # === Bucketed candidate search (3/3 → 2/3 → 1/3) ===
    nft_details = []

    # Pull symbol if present in state (may be None)
    selected_symbol = data.get("selected_symbol")

    # Helper: extract a trait value by name
    def _trait_val(g, name):
        return next((tr.get("value") for tr in g.get("traits", []) if tr.get("type") == name), None)

    # Helper: cheapest listed price across ANY market; +inf if none
    def _min_listed_price(g):
        markets = g.get("markets", {}) or {}
        best = float("inf")
        for m in markets.values():
            try:
                if m.get("is_listed") and "price" in m and "amount" in m["price"]:
                    best = min(best, float(m["price"]["amount"]))
            except Exception:
                continue
        return best

    # Collect a capped set of candidates for performance
    cursor = nfts_collection.find(
        {"collection_uid": collection_uid, "traits": {"$exists": True}},
        projection={"_id": 1, "traits": 1, "markets": 1},
    )
    candidates = await cursor.to_list(length=600)

    exact, partial, model_only = [], [], []
    from itertools import product as _product
    backdrop_combinations = selected_backdrops if selected_backdrops else [None]

    for model, backdrop in _product(selected_models, backdrop_combinations):
        for g in candidates:
            gm, gb, gs = _trait_val(g, "model"), _trait_val(g, "backdrop"), _trait_val(g, "symbol")
            m_eq = (gm == model) if model else False
            b_eq = (gb == backdrop) if backdrop else False
            s_eq = (gs == selected_symbol) if selected_symbol else False
            if m_eq and b_eq and s_eq:
                exact.append(g)
            elif m_eq and b_eq:
                partial.append(g)
            elif m_eq:
                model_only.append(g)

    # Sort each bucket by cheapest listing
    for bucket in (exact, partial, model_only):
        bucket.sort(key=_min_listed_price)

    # Pick best available candidate (exact → partial → model_only)
    chosen = (exact or partial or model_only)
    if chosen:
        nft = chosen[0]
        traits = {t.get("type"): t.get("value") for t in nft.get("traits", [])}

        rarity = None
        for trait in nft.get("traits", []):
            if trait.get("type") == "model" and "rarity_per_mille" in trait:
                try:
                    rarity = int(trait["rarity_per_mille"])
                except Exception:
                    rarity = None
                break

        nft_id = nft.get("_id")
        # use cheapest across markets for display price if needed; fallback 0
        price_amount = _min_listed_price(nft)
        if not (price_amount == price_amount):  # NaN guard (unlikely)
            price_amount = 0.0
        if price_amount == float("inf"):
            price_amount = 0.0

        nft_details.append({
            "id": nft_id,
            "name": str(nft_id).split("|")[-1].replace("-", " ").replace("#", " #").title(),
            "backdrop": traits.get("backdrop", backdrop or ""),
            "price": float(price_amount),
            "est_price": float(await estimate_ton_price(nft_id)) if nft_id else 0.0,
            "rarity": f"{rarity / 10:.1f}%" if rarity is not None else "—",
            "liquidity": int(float((collection.get("markets", {}) or {}).get("portals", {}).get("day_volume", {}).get("amount", 0)))
        })

    print(f"[AI] nft_details_count={len(nft_details)} user_question={user_question!r}")
    print(f"ANALYSIS DATA (detailed): {nft_details}")

    ai_analyse_label = t.get("ai_analyse_gift") or "🔎 Проанализируй подарок"
    if (user_question_key == "ai_analyse_gift") or (user_question == ai_analyse_label):
        print(f"[AI] route_check: matched ai_analyse_gift (key={user_question_key!r}, text_match={user_question == ai_analyse_label})")
        if nft_details:
            try:
                print("[AI] Calling render_forecast() for first item…")
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
            try:
                await msg.answer(t["keyboard_restored"], reply_markup=get_main_menu(t))
            except Exception:
                # на случай, если edit/markup даст ошибку — просто отправим клавиатуру
                await msg.answer(t["keyboard_restored"], reply_markup=get_main_menu(t))
            await state.clear()
            return
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
