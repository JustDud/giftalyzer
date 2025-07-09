from aiogram import Dispatcher
from . import start, id_check, market_search, search_results, admin_support, support #, manual_check, ai_question, help


def register_all_handlers(dp: Dispatcher):
    start.register(dp)
    id_check.register(dp)
    market_search.register(dp)
    search_results.register(dp)
    admin_support.register(dp)
    support.register(dp)
    # manual_check.register(dp)
    # ai_question.register(dp)
    # help.register(dp)