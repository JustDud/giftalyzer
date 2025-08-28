from aiogram import Dispatcher
import importlib

# list submodules we expose lazily
_SUBMODS = {
    "start", "id_check", "market_search", "search_results",
    "admin_support", "support", "payments", "admin_general",
    "language", "ai_requests", "ai_requests_results", "about",
}

def __getattr__(name):
    # allows: from bot_manager.handlers import ai_requests (without cycles)
    if name in _SUBMODS:
        return importlib.import_module(f"{__name__}.{name}")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

def register_all_handlers(dp: Dispatcher):
    # lazy-import submodules to avoid cycles during package init
    start = importlib.import_module(f"{__name__}.start")
    about = importlib.import_module(f"{__name__}.about")
    id_check = importlib.import_module(f"{__name__}.id_check")
    market_search = importlib.import_module(f"{__name__}.market_search")
    search_results = importlib.import_module(f"{__name__}.search_results")
    admin_support = importlib.import_module(f"{__name__}.admin_support")
    support = importlib.import_module(f"{__name__}.support")
    payments = importlib.import_module(f"{__name__}.payments")
    admin_general = importlib.import_module(f"{__name__}.admin_general")
    language = importlib.import_module(f"{__name__}.language")
    ai_requests = importlib.import_module(f"{__name__}.ai_requests")
    ai_requests_results = importlib.import_module(f"{__name__}.ai_requests_results")

    start.register(dp)
    about.register(dp)
    id_check.register(dp)
    market_search.register(dp)
    search_results.register(dp)
    admin_support.register(dp)
    support.register(dp)
    ai_requests.register(dp)
    ai_requests_results.register(dp)
    admin_general.register(dp)
    language.register(dp)
    payments.register(dp)