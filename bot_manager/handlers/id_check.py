from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext
from bot_manager.states.gift_states import GiftStates
from bot_manager.texts import ru as t
from bot_manager.keyboards.default import back_keyboard

from analyser.price_analyser import get_data, estimate_ton_price
import requests

router = Router()


def get_ton_to_usd_rate():
    # url = "https://api.coingecko.com/api/v3/simple/price?ids=toncoin&vs_currencies=usd"
    # response = requests.get(url)
    # if response.status_code != 200:
    #     raise ValueError(f"Failed to fetch TON price. HTTP Status: {response.status_code}")
    # data = response.json()
    # price = data.get("toncoin", {}).get("usd")
    # if price is None:
    #     raise KeyError(f"'toncoin' or 'usd' not found in API response: {data}")
    # return price
    return 2


# Triggered when user presses the button
@router.message(F.text == "🔎 Ввести ID подарка")
async def ask_for_gift_id(message: types.Message, state: FSMContext):
    await state.set_state(GiftStates.WaitingForGiftID)
    await message.answer(t.texts["id_input_prompt"], reply_markup=back_keyboard)


# Handle user ID input
@router.message(GiftStates.WaitingForGiftID)
async def process_gift_id(message: types.Message, state: FSMContext):
    gift_id = message.text.strip()

    data = get_data(gift_id)
    price = estimate_ton_price(gift_id)
    ton_to_usd = get_ton_to_usd_rate()
    usd = round(price * ton_to_usd, 2)

    # TODO: Replace with actual logic to fetch and parse gift info
    result = {
        "name": data["name"],
        "model": data["model"],
        "symbol": data["symbol"],
        "background": data["background"],
        "ton": price,
        "usd": usd,
        "market": data["market"],
        "floor": data["price"]
    }
    print(result)

    await state.clear()
    await message.answer(
        t.texts["gift_result"].format(**result),
        reply_markup=back_keyboard
    )


def register(dp):
    dp.include_router(router)
