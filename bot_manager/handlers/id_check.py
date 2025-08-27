import re
from aiogram import types, Router
from aiogram.fsm.context import FSMContext
from bot_manager.states.gift_states import GiftStates
from bot_manager.keyboards.default import get_check_again_keyboard, get_main_menu, get_back_keyboard

from analyser.price_analyser import estimate_u_shape_by_id, convert_ton_to_usd
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

        # Decide query strategy based on backdrop
        special_backdrops = {"black", "onyx black", "gunmetal"}
        backdrop_key = (parsed_data.get("backdrop") or "").strip().lower()

        if backdrop_key in special_backdrops:
            from mongo import find_exact_then_symbolless
            gift_data = await find_exact_then_symbolless(
                model=parsed_data["model"],
                backdrop=parsed_data["backdrop"],
                symbol=parsed_data.get("symbol"),
                collection_slug=collection_slug,
                require_listed=False,  # broaden search; we'll filter to priced entries below
            )
        else:
            from mongo import find_nfts_by_model
            gift_data = await find_nfts_by_model(
                model=parsed_data["model"],
                collection_slug=collection_slug
            )

        print(f"[🔍 Trait Matching] Matching results: {gift_data}")

        if not gift_data:
            await message.answer(t["no_similar_gifts"])
            await state.set_state(GiftStates.WaitingForGiftID)
            return

        if backdrop_key in special_backdrops:
            # Keep only entries that have a price in any market; pick the cheapest
            def _min_any_market_price(g):
                best = float("inf")
                for m in (g.get("markets", {}) or {}).values():
                    try:
                        amt = float(m.get("price", {}).get("amount"))
                        if amt < best:
                            best = amt
                    except Exception:
                        continue
                return best

            priced = [g for g in gift_data if _min_any_market_price(g) != float("inf")]
            if not priced:
                await message.answer(t["no_similar_gifts"])
                await state.set_state(GiftStates.WaitingForGiftID)
                return

            priced_sorted = sorted(priced, key=_min_any_market_price)
            chosen = priced_sorted[0]

            def _trait_val(g, name):
                return next((tr.get("value") for tr in g.get("traits", []) if tr.get("type") == name), None)

            g_symbol = _trait_val(chosen, "symbol")
            target_symbol = parsed_data.get("symbol")
            is_symbolless = g_symbol is None or str(g_symbol).strip() in {"", "-", "—"}
            if not is_symbolless and target_symbol and str(g_symbol) == target_symbol:
                await message.answer(t["exact_match_found"])
            else:
                await message.answer(t["similar_gifts_found"])

            await send_gift_result(message, chosen, t)
            return
        else:
            # Non-special backdrop: just treat all gift_data as model-only results
            model_only_sorted = sorted(gift_data, key=lambda g: float(g.get("markets", {}).get("portals", {}).get("price", {}).get("amount", float("inf"))))
            await message.answer(t["similar_gifts_found"])
            for gift in model_only_sorted[:1]:
                await send_gift_result(message, gift, t)
            return

    price = await estimate_u_shape_by_id(data["nft_id"])
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
        if "price" in data and "amount" in data["price"]:
            try:
                price = float(data["price"]["amount"])
            except Exception:
                continue
            if price < cheapest_price:
                cheapest_price = price
                cheapest_market = (market_name, data)

    if not cheapest_market:
        await message.answer(t["gift_extraction_failed"])
        return

    market_name, market_info = cheapest_market
    market_price = float(market_info["price"]["amount"])
    estimated_price = await estimate_u_shape_by_id(gift.get("nft_id") or gift.get("_id"))
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
