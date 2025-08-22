from aiogram import BaseMiddleware
from aiogram.types import Message
from typing import Callable, Awaitable, Dict

ALLOWED_USER_IDS = {474039722, 7866461346}

class DevGuardMiddleware(BaseMiddleware):
    async def __call__(self, handler: Callable[[Message, Dict], Awaitable], event: Message, data: Dict):
        if isinstance(event, Message) and event.from_user.id not in ALLOWED_USER_IDS:
            await event.answer("🛠 Бот находится в разработке.")
            return
        return await handler(event, data)