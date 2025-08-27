import inspect
from mongo import users_collection
from aiogram.types import Message, CallbackQuery
from subscription.subscription_manager import is_subscription_valid
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


def ai_access_required(handler):
    async def wrapped(event: Message | CallbackQuery, *args, **kwargs):
        t = await get_texts(event.from_user.id)
        user_id = event.from_user.id

        sig = inspect.signature(handler)
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}

        # If the user has an active subscription, allow without consuming free requests
        try:
            if await is_subscription_valid(user_id):
                return await handler(event, *args, **filtered_kwargs)
        except Exception:
            # If subscription check fails, fall back to free-requests logic
            pass

        user = await users_collection.find_one({"user_id": user_id})
        if not user:
            await users_collection.insert_one({
                "user_id": user_id,
                "first_name": getattr(event.from_user, "first_name", None),
                "last_name": getattr(event.from_user, "last_name", None),
                "username": getattr(event.from_user, "username", None),
                "free_ai_requests": 10,
                "language": "ru"
            })
            return await handler(event, *args, **filtered_kwargs)

        free_left = user.get("free_ai_requests", 0)
        if free_left > 0:
            await users_collection.update_one(
                {"user_id": user_id},
                {"$inc": {"free_ai_requests": -1},
                 "$set": {
                    "first_name": getattr(event.from_user, "first_name", None),
                    "last_name": getattr(event.from_user, "last_name", None),
                    "username": getattr(event.from_user, "username", None),
                 }}
            )
            updated = await users_collection.find_one({"user_id": user_id})
            try:
                try:
                    # Если это CallbackQuery — отправляем обычное текстовое сообщение
                    await event.message.answer(
                        f"🧠 Осталось бесплатных AI-запросов: {updated.get('free_ai_requests', 0)}")
                except AttributeError:
                    # Если это Message — fallback на answer (всё равно отправится в чат)
                    await event.answer(f"🧠 Осталось бесплатных AI-запросов: {updated.get('free_ai_requests', 0)}")
            except Exception:
                pass  # fallback if event is Message

            return await handler(event, *args, **filtered_kwargs)

        try:
            # If CallbackQuery, prefer sending a text message to the chat
            await event.message.answer(t["no_active_subscription"])
        except AttributeError:
            # If Message, answer directly
            await event.answer(t["no_active_subscription"])
    return wrapped