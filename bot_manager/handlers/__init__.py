from aiogram import Dispatcher
from . import (start, id_check, market_search, search_results, admin_support, support, payments,
               admin_general, language, ai_requests, ai_requests_results)


def register_all_handlers(dp: Dispatcher):
    start.register(dp)
    id_check.register(dp)
    market_search.register(dp)
    search_results.register(dp)
    admin_support.register(dp)
    support.register(dp)
    payments.register(dp)
    admin_general.register(dp)
    language.register(dp)
    ai_requests.register(dp)
    ai_requests_results.register(dp)

