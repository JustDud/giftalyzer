import asyncio
from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext
from bot_manager.states.gift_states import GiftStates
from bot_manager.texts import ru as t
from bot_manager.keyboards.default import check_again_keyboard, main_menu, back_keyboard

from analyser.price_analyser import get_data, estimate_ton_price, convert_ton_to_usd
from analyser.page_parser import parse_telegram_gift_page

from mongo import get_nfts_strict_match, get_nfts_loose_match
from mongo import get_nft_by_id_or_name, normalize_nft_name, get_nfts_model_only

from bot_manager.decorators.access import subscription_required

router = Router()


# Triggered when user presses the button
@router.message(F.text == t.texts["btn_enter_id"])
@subscription_required
async def ask_for_gift_id(message: types.Message, state: FSMContext):
    await state.set_state(GiftStates.WaitingForGiftID)
    await message.answer(t.texts["id_input_prompt"], reply_markup=back_keyboard)


@router.message(F.text == t.texts["btn_check_another"])
async def repeat_gift_check(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(t.texts["id_input_prompt"], reply_markup=back_keyboard)
    await state.set_state(GiftStates.WaitingForGiftID)


@router.message(F.text == t.texts["btn_back"])
async def go_back(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(t.texts["returned_to_menu"], reply_markup=main_menu)


# Handle user ID input
@router.message(GiftStates.WaitingForGiftID)
async def process_gift_id(message: types.Message, state: FSMContext):
    gift_id = message.text.strip()

    # Extract gift name or ID from link
    if "/nft/" in gift_id:
        gift_id = gift_id.split("/nft/")[-1]
    elif "/" in gift_id:
        gift_id = gift_id.rsplit("/", 1)[-1]

    gift_id = gift_id.strip().strip("/")
    print(f"[DEBUG] Normalized gift_id: {gift_id}")
    await state.clear()  # Clear early to prevent lingering state

    normalized_id = gift_id.strip().strip("/")
    # Check if it's a name-formatted input
    if "-" in normalized_id and not normalized_id.startswith("EQ"):
        normalized_id = normalize_nft_name(normalized_id)

    data = get_nft_by_id_or_name(normalized_id)
    if data is None:
        # Попытка парсить страницу Telegram подарка
        parsed_data = await parse_telegram_gift_page(normalized_id)
        print(f"[DEBUG] Parsed data from Telegram page: {parsed_data}")

        # Убираем цифры и дефисы, чтобы извлечь название коллекции
        import re
        collection_name = re.sub(r'\d+', '', normalized_id.split("-")[0])

        if parsed_data is None:
            await message.answer("❌ Не удалось извлечь параметры подарка. Возможно, ссылка недействительна или структура страницы изменилась.")
            await state.set_state(GiftStates.WaitingForGiftID)
            return

        # Ищем сначала по всем трём параметрам
        strict = get_nfts_strict_match(
            model=parsed_data["model"],
            symbol=parsed_data["symbol"],
            backdrop=parsed_data["backdrop"],
            collection_name=collection_name
        )

        # Затем ищем совпадения без символа
        loose = get_nfts_loose_match(
            model=parsed_data["model"],
            backdrop=parsed_data["backdrop"],
            collection_name=collection_name
        )

        # Убираем дубликаты
        strict_ids = {gift["nft_id"] for gift in strict}
        loose_filtered = [gift for gift in loose if gift["nft_id"] not in strict_ids]

        # Затем ищем только по модели (если ничего не нашли)
        model_only = get_nfts_model_only(
            model=parsed_data["model"],
            collection_name=collection_name
        )

        # Убираем уже найденные ранее
        all_found_ids = strict_ids.union({gift["nft_id"] for gift in loose_filtered})
        model_only_filtered = [gift for gift in model_only if gift["nft_id"] not in all_found_ids]

        if not (strict or loose_filtered or model_only_filtered):
            await message.answer("⚠️ Похожих подарков не найдено. Возможно, ваш подарок уникален или ещё не добавлен в базу. Попробуйте другое ID")
            await state.set_state(GiftStates.WaitingForGiftID)
            return

        # Сортируем каждую группу отдельно
        strict_sorted = sorted(strict, key=lambda x: float(x["price"]))
        loose_sorted = sorted(loose_filtered, key=lambda x: float(x["price"]))
        model_only_sorted = sorted(model_only_filtered, key=lambda x: float(x["price"]))

        result_found = False

        if strict_sorted:
            await message.answer("✅ Найдены подарки с полной идентичностью (модель, символ, фон):")
            for gift in strict_sorted[:5]:
                await send_gift_result(message, gift)
            result_found = True

        if not result_found and loose_sorted:
            await message.answer("⚠️ Найдены похожие подарки без совпадения по символу:")
            for gift in loose_sorted[:5]:
                await send_gift_result(message, gift)
            result_found = True

        if not result_found and model_only_sorted:
            await message.answer("🔍 Найдены подарки только с совпадением по модели:")
            for gift in model_only_sorted[:5]:
                await send_gift_result(message, gift)
            result_found = True

        if not result_found:
            await message.answer("😔 К сожалению, не удалось найти ни одного похожего подарка.")
        return

    price = estimate_ton_price(data["nft_id"])
    usd_estimated = convert_ton_to_usd(price)
    usd_market = convert_ton_to_usd(float(data["price"]))
    await send_gift_result(message, {
        "name": data["name"],
        "model": data["model"],
        "symbol": data["symbol"],
        "backdrop": data["backdrop"],
        "price": price,
        "market_price": data["price"],
        "market": data["market"],
        "nft_id": data["nft_id"]
    })



@router.message(GiftStates.WaitingForManualInput)
async def process_manual_input(message: types.Message, state: FSMContext):
    await state.clear()  # Clear early to prevent lingering state
    text = message.text.strip()
    # Here you would parse model, background, etc.
    # For now, just return placeholders
    result = {
        "name": "Custom Gift",
        "model": "ManualModel",
        "symbol": "ManualSymbol",
        "background": "ManualBackground",
        "ton": 500.0,
        "usd_estimated": convert_ton_to_usd(500.0),
        "market": "N/A",
        "market_price": 0.0,
        "usd_market": 0.0
    }

    await message.answer(
        t.texts["gift_result"].format(**result),
        reply_markup=check_again_keyboard
    )


async def send_gift_result(message: types.Message, gift: dict):
    estimated_price = estimate_ton_price(gift["nft_id"]) if "nft_id" in gift else float(gift["price"])
    market_price = float(gift["price"])

    usd_estimated = convert_ton_to_usd(estimated_price)
    usd_market = convert_ton_to_usd(market_price) if market_price is not None else "—"

    result = {
        "name": gift["name"],
        "model": gift["model"],
        "symbol": gift["symbol"],
        "backdrop": gift["backdrop"],
        "ton": estimated_price,
        "usd_estimated": usd_estimated,
        "market": gift.get("market", "N/A"),
        "market_price": market_price if market_price is not None else "—",
        "usd_market": usd_market
    }

    await message.answer(
        t.texts["gift_result"].format(**result),
        reply_markup=check_again_keyboard
    )

def register(dp):
    dp.include_router(router)
