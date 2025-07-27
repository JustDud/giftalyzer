from aiogram.types import CallbackQuery

async def show_ai_results(call: CallbackQuery, ai_response: str):
    """
    Simply outputs the AI response as plain text in the chat.
    In the future, formatting and interactive buttons can be added here.
    """
    await call.message.answer(f"📊 Результат анализа:\n\n{ai_response}")
