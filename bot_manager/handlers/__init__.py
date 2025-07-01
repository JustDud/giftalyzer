from aiogram import Dispatcher
from . import start, id_check #, manual_check, ai_question, help


def register_all_handlers(dp: Dispatcher):
    start.register(dp)
    id_check.register(dp)
    # manual_check.register(dp)
    # ai_question.register(dp)
    # help.register(dp)