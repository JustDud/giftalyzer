import re
from aiogram import types, Router
from aiogram.fsm.context import FSMContext
from bot_manager.states.gift_states import GiftStates
from bot_manager.keyboards.default import get_check_again_keyboard, get_main_menu, get_back_keyboard

from analyser.price_analyser import estimate_ton_price, convert_ton_to_usd
from analyser.page_parser import parse_telegram_gift_page

from mongo import get_nft_by_id_or_name, normalize_nft_name
from mongo import find_nft_id_by_traits_flexible

from bot_manager.decorators.access import subscription_required

router = Router()


@router.message(lambda msg, t: msg.text == t["btn_enter_id"])
@subscription_required
async def ask_for_gift_id(message: types.Message, state: FSMContext, t: dict):
    await state.set_state(GiftStates.WaitingForGiftID)
    await message.answer(t["id_input_prompt"], reply_markup=get_back_keyboard(t))


@router.message(lambda msg, t: msg.text == t["btn_check_another"])
async def repeat_gift_check(message: types.Message, state: FSMContext, t: dict):
    await state.clear()
    await message.answer(t["id_input_prompt"], reply_markup=get_back_keyboard(t))
    await state.set_state(GiftStates.WaitingForGiftID)


@router.message(lambda msg, t: msg.text == t["btn_back"])
async def go_back(message: types.Message, state: FSMContext, t: dict):
    await state.clear()
    await message.answer(t["returned_to_menu"], reply_markup=get_main_menu(t))


# Handle user ID input
@router.message(GiftStates.WaitingForGiftID)
async def process_gift_id(message: types.Message, state: FSMContext, t: dict):
    gift_id = message.text.strip()

    # Extract gift name or ID from link
    if "/nft/" in gift_id:
        gift_id = gift_id.split("/nft/")[-1]
    elif "/" in gift_id:
        gift_id = gift_id.rsplit("/", 1)[-1]

    gift_id = gift_id.strip().strip("/")
    await state.clear()

    normalized_id = gift_id.strip().strip("/")
    if "-" in normalized_id and not normalized_id.startswith("EQ"):
        normalized_id = normalize_nft_name(normalized_id)

    data = await get_nft_by_id_or_name(normalized_id)
    if data is None:
        parsed_data = await parse_telegram_gift_page(normalized_id)
        print(f"[🔍 Trait Matching] Parsed traits: {parsed_data}")

        collection_name = re.sub(r'\d+', '', normalized_id.split("-")[0])
        # Normalize collection slug to match DB format (e.g. SnoopCigar -> snoop-cigar)
        import re as _re
        collection_slug = _re.sub(r'(?<!^)(?=[A-Z])', '-', collection_name).lower()
        print(f"[🔍 Trait Matching] Collection slug: {collection_slug}")

        if parsed_data is None:
            await message.answer(t["gift_extraction_failed"])
            await state.set_state(GiftStates.WaitingForGiftID)
            return

        gift_data = await find_nft_id_by_traits_flexible(
            model=parsed_data["model"],
            backdrop=parsed_data["backdrop"],
            symbol=parsed_data["symbol"],
            collection_slug=collection_slug
        )
        print(f"[🔍 Trait Matching] Matching results: {gift_data}")

        if not gift_data:
            await message.answer(t["no_similar_gifts"])
            await state.set_state(GiftStates.WaitingForGiftID)
            return

        # Classify matches: 3/3 (model, backdrop, symbol), 2/3 (model + backdrop), 1/3 (model only)
        target_model = parsed_data.get("model")
        target_backdrop = parsed_data.get("backdrop")
        target_symbol = parsed_data.get("symbol")

        def _trait_val(g, name):
            return next((tr.get("value") for tr in g.get("traits", []) if tr.get("type") == name), None)

        exact = []
        partial = []
        model_only = []
        for g in gift_data:
            g_model = _trait_val(g, "model")
            g_backdrop = _trait_val(g, "backdrop")
            g_symbol = _trait_val(g, "symbol")

            m_eq = (g_model == target_model) if target_model else False
            b_eq = (g_backdrop == target_backdrop) if target_backdrop else False
            s_eq = (g_symbol == target_symbol) if target_symbol else False

            if m_eq and b_eq and s_eq:
                exact.append(g)
            elif m_eq and b_eq:
                partial.append(g)
            elif m_eq:
                model_only.append(g)

        # Helper: return the cheapest listed price across ANY market (fallback to +inf if none)
        def _min_listed_price(g):
            markets = g.get("markets", {}) or {}
            best = float("inf")
            for _, m in markets.items():
                try:
                    if m.get("is_listed") and "price" in m and "amount" in m["price"]:
                        p = float(m["price"]["amount"])
                        if p < best:
                            best = p
                except Exception:
                    continue
            return best

        sent_any = False
        if exact:
            exact_sorted = sorted(exact, key=_min_listed_price)
            await message.answer(t["exact_match_found"])
            for gift in exact_sorted[:1]:
                await send_gift_result(message, gift, t)
            sent_any = True

        if partial:
            partial_sorted = sorted(partial, key=_min_listed_price)
            await message.answer(t["similar_gifts_found"])
            for gift in partial_sorted[:1]:
                await send_gift_result(message, gift, t)
            sent_any = True

        if model_only:
            model_only_sorted = sorted(model_only, key=_min_listed_price)
            await message.answer(t["model_only_match_found"])
            for gift in model_only_sorted[:1]:
                await send_gift_result(message, gift, t)
            sent_any = True

        if not sent_any:
            await message.answer(t["no_similar_gifts"])
            await state.set_state(GiftStates.WaitingForGiftID)
            return

        return

    price = await estimate_ton_price(data["nft_id"])
    await send_gift_result(message, {
        "name": data["name"],
        "model": data["model"],
        "symbol": data["symbol"],
        "backdrop": data["backdrop"],
        "price": price,
        "market_price": data["price"],
        "market": data["market"],
        "nft_id": data["nft_id"]
    }, t)


async def send_gift_result(message: types.Message, gift: dict, t: dict):
    market_data = gift.get("markets", {})
    if not market_data:
        await message.answer(t["gift_extraction_failed"])
        return

    # Pick cheapest available listing across markets
    cheapest_market = None
    cheapest_price = float("inf")
    for market_name, data in market_data.items():
        if data.get("is_listed") and "price" in data:
            price = float(data["price"]["amount"])
            if price < cheapest_price:
                cheapest_price = price
                cheapest_market = (market_name, data)

    if not cheapest_market:
        await message.answer(t["gift_extraction_failed"])
        return

    market_name, market_info = cheapest_market
    market_price = float(market_info["price"]["amount"])
    estimated_price = await estimate_ton_price(gift.get("nft_id") or gift.get("_id"))
    usd_estimated = await convert_ton_to_usd(estimated_price)
    usd_market = await convert_ton_to_usd(market_price)

    result = {
        "name": gift["name"],
        "model": next((t["value"] for t in gift.get("traits", []) if t["type"] == "model"), "—"),
        "symbol": next((t["value"] for t in gift.get("traits", []) if t["type"] == "symbol"), "—"),
        "backdrop": next((t["value"] for t in gift.get("traits", []) if t["type"] == "backdrop"), "—"),
        "ton": estimated_price,
        "usd_estimated": usd_estimated,
        "market": market_name,
        "market_price": market_price,
        "usd_market": usd_market,
        "nft_id": gift.get("nft_id") or gift.get("_id"),
    }

    await message.answer(
        t["gift_result"].format(**result),
        reply_markup=get_check_again_keyboard(t)
    )


def register(dp):
    dp.include_router(router)
