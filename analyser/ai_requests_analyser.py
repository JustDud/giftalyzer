from analyser.model_provider import generate_response
from mongo import nfts_collection
import json


async def analyse_ai_request(call, state, t):
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
                "estimated_ton": float(nft.get("estimated_ton", 0)),
                "symbol": nft.get("symbol", ""),
                "volume_of_sales": int(nft.get("volume_of_sales", 0))
            })

    print(f"ANALYSIS DATA (detailed): {nft_details}")

    # Choose the system prompt
    if user_question == "🔍 Проанализируй NFT":
        system_prompt = "Ты — ведущий аналитик цифрового рынка NFT. На основе предоставленных данных проведи детальный анализ и выдай краткий, уверенный прогноз движения цены: up, neutral или down. Сравни до двух NFT, если данные указаны, и учти любые доступные рыночные тренды на 27 июля 2025 года или актуальнее, если возможно. Используй следующую логику:\n\nРедкость: < 50,000 → +1, > 75,000 → -1, иначе 0\nЦена vs оценка: < 95% от estimated_ton → +1, > 105% от estimated_ton → -1, иначе 0\nПопулярные атрибуты: наличие Neon Blue, Caramel, Cotton Candy, Indigo Dye, Navy Blue → +1, иначе 0\nОбъем продаж: > 100 → +1, иначе 0\nСумма баллов: ≥ 2 → up, ≤ -2 → down, между -1 и 1 → neutral\n\nФорматируй ответ в следующем виде:\n\nОбоснование:\nНачни с уверенного вывода о динамике цены в ближайшие 30 дней для каждого NFT. Затем по пунктам объясни влияние факторов:\nРедкость: укажи значение и его рыночное значение (редкий, распространенный или нейтральный).\nСравнение цены с оценочной: проанализируй отклонение и его влияние на ценность.\nПопулярные атрибуты: отметь наличие популярных черт и их эффект на спрос.\nРыночная активность: прокомментируй объем продаж и его роль в ликвидности.\nИтог: подведи итог с акцентом на формирующийся тренд или стабильность.\nПрогноз: up / neutral / down\nПример входных данных:\n\n{\n\n\"nft_id\": \"EQDmbKmCH8r2egTHXYLaL10iQvbIZSzFanlexW5aaX5aFm6H\",\n\n\"rarity\": 2114,\n\n\"real_price\": 420,\n\n\"estimated_ton\": 478.8,\n\n\"backdrop\": \"Navy Blue\",\n\n\"model\": \"Party-Ready\",\n\n\"symbol\": \"Cocktail\",\n\n\"volume_of_sales\": 185\n\n},\n\n{\n\n\"nft_id\": \"EQBWQcgVQtFTLqIpFhwbp5oW4MPxkoL9sSUYv1d-dHBcjsI3\",\n\n\"rarity\": 100850,\n\n\"real_price\": 7000,\n\n\"estimated_ton\": 4025.0,\n\n\"backdrop\": \"Sapphire\",\n\n\"model\": \"Birmingham\",\n\n\"symbol\": \"Ice Pop\",\n\n\"volume_of_sales\": 40\n\n}\n\nОжидаемый ответ для примера:\n\nОбоснование:\n\nДля NFT EQDmbKmCH8r2egTHXYLaL10iQvbIZSzFanlexW5aaX5aFm6H цена с высокой вероятностью продемонстрирует устойчивый рост в ближайшие 30 дней.\n\nРедкость: 2114 отражает исключительную редкость актива, усиливая его ценность.\nСравнение цены с оценочной: цена 420 на 12% ниже 478.8, подтверждая недооценку с потенциалом роста.\nПопулярные атрибуты: наличие Navy Blue гарантирует повышенный спрос.\nРыночная активность: объем продаж 185 подтверждает высокий уровень ликвидности.\nИтог: совокупность факторов формирует убедительный восходящий тренд.\nДля NFT EQBWQcgVQtFTLqIpF"
    elif user_question == "📈 Покажи недооцененные":
        system_prompt = "TEMPLATE: add undervalued NFT analysis prompt here"
    elif user_question == "⬆ Только с прогнозом 'up'":
        system_prompt = "TEMPLATE: add only-up forecast analysis prompt here"
    else:
        system_prompt = "TEMPLATE: default prompt"

    try:
        import json
        ai_response = await generate_response(system_prompt, json.dumps(nft_details, ensure_ascii=False))
        await call.message.edit_text(f"📊 Результат анализа:\n\n{ai_response}")
    except Exception as e:
        import logging
        logging.exception("AI request failed: %s", e)
        await call.message.edit_text("❌ Не удалось получить ответ от AI. Попробуйте позже.")
    finally:
        await state.clear()  # или верни в главное меню, если нужно


