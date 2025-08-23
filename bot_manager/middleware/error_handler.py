import logging
from aiogram import types
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest


async def global_error_handler(update: types.Update, exception: Exception):
    if isinstance(exception, TelegramForbiddenError):
        user_id = update.message.from_user.id if update.message else "unknown"
        logging.warning(f"User {user_id} blocked the bot.")
        return True  # suppress traceback

    if isinstance(exception, TelegramBadRequest) and "message is not modified" in str(exception):
        # Happens when editing with same text — not critical
        return True

    logging.exception("Unexpected exception occurred", exc_info=exception)
    return True  # suppress traceback