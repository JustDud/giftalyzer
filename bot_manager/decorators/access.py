from aiogram.types import Message
from subscription.manager import is_subscription_valid
from bot_manager.texts import get_texts


def subscription_required(handler):
    async def wrapped(message: Message, *args, **kwargs):
        t = await get_texts(message.from_user.id)
        # Filter out unexpected kwargs (e.g. 'dispatcher' passed by aiogram)
        filtered_kwargs = {
            k: v for k, v in kwargs.items()
            if k in handler.__code__.co_varnames
        }
        if await is_subscription_valid(message.from_user.id):
            return await handler(message, *args, **filtered_kwargs)
        await message.answer(t["no_active_subscription"])
    return wrapped
