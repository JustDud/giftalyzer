import logging
from aiogram import types
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest


async def global_error_handler(event: types.TelegramObject, data: dict):
    """Global error handler compatible with aiogram 3.x ErrorMiddleware.
    It receives (event, data), where data contains the raised `exception`.
    Return True to suppress further propagation/traceback.
    """
    exception = data.get("exception")

    # Gracefully ignore forbidden errors (bot blocked by user)
    if isinstance(exception, TelegramForbiddenError):
        try:
            # event could be Message, CallbackQuery, etc.
            user_id = getattr(getattr(event, "from_user", None), "id", None)
            if user_id is None and hasattr(event, "message"):
                user_id = getattr(getattr(event.message, "from_user", None), "id", "unknown")
        except Exception:
            user_id = "unknown"
        logging.warning(f"User {user_id} blocked the bot.")
        return True  # suppress traceback

    # Benign: editing message with identical content
    if isinstance(exception, TelegramBadRequest) and "message is not modified" in str(exception).lower():
        return True

    # Log unexpected exceptions with stack trace
    logging.exception("Unexpected exception occurred", exc_info=exception)
    return True