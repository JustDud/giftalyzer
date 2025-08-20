from analyser.model_provider import generate_response
from analyser.price_analyser import estimate_ton_price
from mongo import nfts_collection
import json
from bot_manager.keyboards.default import get_main_menu
from aiogram.exceptions import TelegramBadRequest
from analyser.forecaster import render_forecast, render_many, render_response, calculate_forecast
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
                "collection": selected_collection,
                "model": traits.get("model", model),
                "backdrop": traits.get("backdrop", backdrop or ""),
                "nft_id": nft_id,  # full ID used for analysis
                "display_name": nft_id.split("|")[-1].replace("-", " ").replace("#", " #").title(),
                "rarity": rarity if rarity is not None else 99999,
                "real_price": float(nft.get("markets", {}).get("portals", {}).get("price", {}).get("amount", 0)),
                "estimated_ton": float(await estimate_ton_price(nft_id)) if nft_id else 0.0,
                "symbol": traits.get("symbol", ""),
                "volume_of_sales": volume_of_sales
            })

    print(f"ANALYSIS DATA (detailed): {nft_details}")

    nft_details = calculate_forecast(nft_details)

    # Choose the system prompt
    if user_question == "🔍 Проанализируй NFT":
        system_prompt = (
            "Ты — ведущий аналитик цифрового рынка NFT. На основе предоставленных данных проведи детальный анализ и выдай краткий, уверенный прогноз движения цены: up, neutral или down. "
            "Сравни до двух NFT, если данные указаны, и учти любые доступные рыночные тренды на 27 июля 2025 года, если возможно. Используй следующую логику:\n\n"
            "Редкость: < 50,000 → +1, > 75,000 → -1, иначе 0\n"
            "Цена vs оценка: < 95% от estimated_ton → +1, > 105% от estimated_ton → -1, иначе 0\n"
            "Популярные атрибуты: наличие Neon Blue, Caramel, Cotton Candy, Indigo Dye, Navy Blue → +1, иначе 0\n"
            "Объем продаж: > 100 → +1, иначе 0\n"
            "Сумма баллов: ≥ 2 → up, ≤ -2 → down, между -1 и 1 → neutral\n\n"
            "Форматируй ответ в следующем виде:\n\n"
            "Обоснование:\n\n"
            "Начни с уверенного вывода о динамике цены в ближайшие 30 дней для каждого NFT. Затем по пунктам объясни влияние факторов:\n"
            "Редкость: укажи значение и его рыночное значение (редкий, распространенный или нейтральный).\n"
            "Сравнение цены с оценочной: проанализируй отклонение и его влияние на ценность.\n"
            "Популярные атрибуты: отметь наличие популярных черт и их эффект на спрос.\n"
            "Рыночная активность: прокомментируй объем продаж и его роль в ликвидности.\n"
            "Итог: подведи итог с акцентом на формирующийся тренд или стабильность.\n"
            "Прогноз: up / neutral / down\n\n"
            "Пример входных данных:\n\n"
            "{\n"
            "\"nft_id\": \"EQDmbKmCH8r2egTHXYLaL10iQvbIZSzFanlexW5aaX5aFm6H\",\n"
            "\"rarity\": 2114,\n"
            "\"real_price\": 420,\n"
            "\"estimated_ton\": 478.8,\n"
            "\"backdrop\": \"Navy Blue\",\n"
            "\"model\": \"Party-Ready\",\n"
            "\"symbol\": \"Cocktail\",\n"
            "\"volume_of_sales\": 185\n"
            "},\n"
            "{\n"
            "\"nft_id\": \"EQBWQcgVQtFTLqIpFhwbp5oW4MPxkoL9sSUYv1d-dHBcjsI3\",\n"
            "\"rarity\": 100850,\n"
            "\"real_price\": 7000,\n"
            "\"estimated_ton\": 4025.0,\n"
            "\"backdrop\": \"Sapphire\",\n"
            "\"model\": \"Birmingham\",\n"
            "\"symbol\": \"Ice Pop\",\n"
            "\"volume_of_sales\": 40\n"
            "}\n\n"
            "Ожидаемый ответ для примера:\n\n"
            "Для NFT EQDmbKmCH8r2egTHXYLaL10iQvbIZSzFanlexW5aaX5aFm6H цена с высокой вероятностью продемонстрирует устойчивый рост в ближайшие 30 дней.\n\n"
            "Редкость: 2114 отражает исключительную редкость актива, усиливая его ценность.\n"
            "Сравнение цены с оценочной: цена 420 на 12% ниже 478.8, подтверждая недооценку с потенциалом роста.\n"
            "Популярные атрибуты: наличие Navy Blue гарантирует повышенный спрос.\n"
            "Рыночная активность: объем продаж 185 подтверждает высокий уровень ликвидности.\n"
            "Итог: совокупность факторов формирует убедительный восходящий тренд."
        )
    elif user_question == "📈 Покажи недооцененные":
        system_prompt = "TEMPLATE: add undervalued NFT analysis prompt here"
    elif user_question == "⬆ Только с прогнозом 'up'":
        system_prompt = "TEMPLATE: add only-up forecast analysis prompt here"
    else:
        system_prompt = "TEMPLATE: default prompt"

    try:
        ai_response = await generate_response(system_prompt, json.dumps(nft_details, ensure_ascii=False, indent=2))
        if not ai_response or "Прогноз" not in ai_response:
            print("⚠️ Falling back to render_forecast...")
            ai_response = render_response(nft_details, user_question)

        # Commented out escape_md_v2 function and related code
        # import re
        # def escape_md_v2(text):
        #     return re.sub(r'([_\*\[\]\(\)\~\`\>\#\+\-\=\|\{\}\.\!\\])', r'\\\1', text)

        for nft in nft_details:
            ai_response = ai_response.replace(nft["nft_id"], nft["display_name"])
        ai_response = ai_response.replace("*", "")
        ai_response = ai_response.replace("#", "")

        try:
            if len(ai_response) <= 4000:
                await msg.answer(ai_response)
            else:
                for chunk in [ai_response[i:i+4000] for i in range(0, len(ai_response), 4000)]:
                    await msg.answer(chunk)
        except Exception as send_error:
            import logging
            logging.exception("❌ Ошибка при отправке AI-ответа: %s", send_error)
            await msg.answer("❌ Не удалось отправить результат. Попробуй позже.")
    except Exception as e:
        import logging
        logging.exception("AI request failed: %s", e)
        try:
            await msg.edit_text("❌ Не удалось получить ответ от AI. Попробуйте позже.")
        except TelegramBadRequest as e2:
            if "message is not modified" not in str(e2):
                raise
    finally:
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
        await msg.answer("✅ Функциональность восстановлена.", reply_markup=get_main_menu(t))
        try:
            await temp.delete()
        except:
            pass
        await state.clear()  # или верни в главное меню, если нужно
