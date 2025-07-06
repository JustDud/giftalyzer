import asyncio
from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext
from bot_manager.states.gift_states import GiftStates
from bot_manager.texts import ru as t
from bot_manager.keyboards.default import check_again_keyboard, main_menu, back_keyboard

from analyser.price_analyser import get_data, estimate_ton_price, convert_ton_to_usd

router = Router()


# Triggered when user presses the button
@router.message(F.text == t.texts["btn_enter_id"])
async def ask_for_gift_id(message: types.Message, state: FSMContext):
    await state.set_state(GiftStates.WaitingForGiftID)
    await message.answer(t.texts["id_input_prompt"], reply_markup=back_keyboard)


# Handle user ID input
@router.message(GiftStates.WaitingForGiftID)
async def process_gift_id(message: types.Message, state: FSMContext):
    gift_id = message.text.strip()
    await state.clear()  # Clear early to prevent lingering state

    try:
        data = get_data(gift_id)
    except ValueError:
        await state.set_state(GiftStates.WaitingForGiftID)  # Re-set the state so user can retry
        await message.answer(t.texts["nft_not_found"], reply_markup=check_again_keyboard)
        return

    price = estimate_ton_price(gift_id)
    usd_estimated = convert_ton_to_usd(price)
    usd_market = convert_ton_to_usd(data["price"])

    result = {
        "name": data["name"],
        "model": data["model"],
        "symbol": data["symbol"],
        "background": data["background"],
        "ton": price,
        "usd_estimated": usd_estimated,
        "market": data["market"],
        "market_price": data["price"],
        "usd_market": usd_market
    }
    print(result)

    await message.answer(
        t.texts["gift_result"].format(**result),
        reply_markup=check_again_keyboard
    )
    await state.clear()



@router.message(F.text == t.texts["btn_check_another"])
async def repeat_gift_check(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(t.texts["id_input_prompt"], reply_markup=back_keyboard)
    await state.set_state(GiftStates.WaitingForGiftID)


@router.message(F.text == t.texts["btn_back"])
async def go_back(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(t.texts["start"], reply_markup=main_menu)

@router.message(GiftStates.WaitingForManualInput)
async def process_manual_input(message: types.Message, state: FSMContext):
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
    await state.clear()


def register(dp):
    dp.include_router(router)
