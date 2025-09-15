from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram import Router, F
import re
from bot_manager.keyboards.default import get_main_menu

router = Router()


@router.message(F.state == "AIResultsState:displaying_results")
async def show_ai_analysis_results(message: Message, state: FSMContext, t: dict):
    ai_response = t.get("ai_analysis") or (await state.get_data()).get("ai_analysis", "")
    if not ai_response:
        await message.answer(t["ai_no_analysis_found"])
        return

    nft_details = t.get("nft_details", [])
    for nft in nft_details:
        ai_response = ai_response.replace(nft["nft_id"], nft["display_name"])

    # Send NFT images (if available) with short captions before the analysis
    for nft in nft_details:
        img = (nft.get("media") or {}).get("image_url") or nft.get("image_url")
        name = nft.get("display_name") or nft.get("name") or nft.get("nft_id")
        if img:
            caption = f"{name}"
            try:
                await message.answer_photo(photo=img, caption=caption[:1024])
            except Exception as e:
                print(f"[⚠] Failed to send NFT image for {name}: {e}")

    if len(ai_response) <= 4000:
        await message.answer(t["ai_analysis_result_prefix"] + "\n\n" + ai_response)
    else:
        for chunk in [ai_response[i:i+4000] for i in range(0, len(ai_response), 4000)]:
            await message.answer(chunk, parse_mode="MarkdownV2")

    await state.clear()

    try:
        await message.answer(t["keyboard_restored"], reply_markup=get_main_menu(t))
    except Exception as e:
        print(f"[❌] Failed to edit message: {e}")


def register(dp):
    dp.include_router(router)