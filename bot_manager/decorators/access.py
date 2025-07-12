from aiogram.types import Message
from subscription.manager import is_subscription_valid

def subscription_required(handler):
    async def wrapped(message: Message, *args, **kwargs):
        # Filter out unexpected kwargs (e.g. 'dispatcher' passed by aiogram)
        filtered_kwargs = {
            k: v for k, v in kwargs.items()
            if k in handler.__code__.co_varnames
        }
        if is_subscription_valid(message.from_user.id):
            return await handler(message, *args, **filtered_kwargs)
        await message.answer("❌ У вас нет активной подписки. Приобретите её, чтобы использовать эту функцию.")
    return wrapped