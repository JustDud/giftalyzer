from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram import Router, F

router = Router()

@router.message(F.state == "AIResultsState:displaying_results")
async def show_ai_analysis_results(message: Message, state: FSMContext, t: dict):
    ai_response = t.get("ai_analysis") or (await state.get_data()).get("ai_analysis", "")
    if not ai_response:
        await message.answer("❌ Анализ не найден.")
        return
    if len(ai_response) <= 4000:
        await message.answer(f"📊 Результат анализа:\n\n{ai_response}")
    else:
        for chunk in [ai_response[i:i+4000] for i in range(0, len(ai_response), 4000)]:
            await message.answer(chunk)
    await state.clear()