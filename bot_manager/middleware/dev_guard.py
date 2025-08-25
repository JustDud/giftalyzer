from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Callable, Awaitable, Dict
from aiogram.fsm.context import FSMContext

ALLOWED_USER_IDS = {474039722, 7866461346, 444450069, 7540264011}


class DevGuardMiddlewareWithSupportBypass(BaseMiddleware):
    async def __call__(self, handler: Callable[[Message, Dict], Awaitable], event, data: Dict):
        if isinstance(event, Message):
            # Allow support-related commands and active FSM sessions
            text = (event.text or "").lower()
            fsm: FSMContext = data.get("state")
            if ("/support" in text or "support" in text) or (fsm and await fsm.get_state()):
                return await handler(event, data)

            if event.from_user.id not in ALLOWED_USER_IDS:
                await event.answer("🛠 Бот находится в разработке. Чтобы обратиться в тех поддержку - /support\n\nBot is in development. To contact support - /support")
                return
        elif isinstance(event, CallbackQuery):
            callback_data = (event.data or "").lower()
            fsm: FSMContext = data.get("state")
            if "support" in callback_data or "help" in callback_data or (fsm and await fsm.get_state()):
                return await handler(event, data)

            if event.from_user.id not in ALLOWED_USER_IDS:
                await event.answer("🛠 Бот находится в разработке. Чтобы обратиться в тех поддержку - /support\n\nBot is in development. To contact support - /support")
                return
        return await handler(event, data)

# Preserve original name
DevGuardMiddleware = DevGuardMiddlewareWithSupportBypass
