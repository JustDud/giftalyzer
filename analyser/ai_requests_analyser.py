from analyser.model_provider import generate_response
from analyser.price_analyser import estimate_ton_price
from mongo import nfts_collection
import json
from bot_manager.keyboards.default import get_main_menu
from aiogram.exceptions import TelegramBadRequest
async def analyse_ai_request(call, state, t, temp):
    data = await state.get_data()
    user_question = data.get("user_question")
    selected_models = data.get("selected_models", [])
    selected_backdrops = data.get("selected_backdrops", [])
    selected_collection = data.get("selected_collection")

    # Get collection address by name
    from mongo import collections_collection
    collection = await collections_collection.find_one({"name": selected_collection})
    if not collection:
        await call.message.answer(f"❌ Коллекция '{selected_collection}' не найдена.")
        return

    collection_address = collection["address"]

    nft_details = []
    for model in selected_models:
        query = {
            "collection_address": collection_address,
            "model": model
        }
        if selected_backdrops:
            query["backdrop"] = {"$in": selected_backdrops}

        async for nft in nfts_collection.find(query):
            nft_details.append({
                "collection": selected_collection,
                "model": nft.get("model", model),
                "backdrop": nft.get("backdrop", ""),
                "nft_id": nft.get("nft_id", ""),
                "rarity": int(nft.get("rarity", 0)),
                "real_price": float(nft.get("price", 0)),
                "estimated_ton": float(await estimate_ton_price(nft.get("nft_id"))) if nft.get("nft_id") else 0.0,
                "symbol": nft.get("symbol", ""),
                "volume_of_sales": int(nft.get("volume_of_sales", 0))
            })

    print(f"ANALYSIS DATA (detailed): {nft_details}")

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
        ai_response = await generate_response(system_prompt, json.dumps(nft_details, ensure_ascii=False))
        try:
            if len(ai_response) <= 4000:
                await call.message.answer(f"📊 Результат анализа:\n\n{ai_response}", parse_mode="MarkdownV2")
            else:
                for chunk in [ai_response[i:i+4000] for i in range(0, len(ai_response), 4000)]:
                    await call.message.answer(f"{chunk}", parse_mode="MarkdownV2")
        except Exception as send_error:
            import logging
            logging.exception("❌ Ошибка при отправке AI-ответа: %s", send_error)
            await call.message.answer("❌ Не удалось отправить результат. Попробуй позже.")
    except Exception as e:
        import logging
        logging.exception("AI request failed: %s", e)
        try:
            await call.message.edit_text("❌ Не удалось получить ответ от AI. Попробуйте позже.")
        except TelegramBadRequest as e2:
            if "message is not modified" not in str(e2):
                raise
    finally:
        # Restore the main menu keyboard safely: clear inline keyboard if needed, then send confirmation with reply keyboard
        from aiogram.types import InlineKeyboardMarkup
        current_reply_markup = call.message.reply_markup
        if current_reply_markup and getattr(current_reply_markup, "inline_keyboard", None):
            if current_reply_markup.inline_keyboard:
                try:
                    try:
                        await call.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=[]))
                    except TelegramBadRequest as e:
                        if "message is not modified" not in str(e):
                            raise
                except Exception as e:
                    import logging
                    logging.warning(f"⚠️ Failed to edit reply markup: {e}")
        await call.message.answer("✅ Функциональность восстановлена.", reply_markup=get_main_menu(t))
        try:
            await temp.delete()
        except:
            pass
        await state.clear()  # или верни в главное меню, если нужно
