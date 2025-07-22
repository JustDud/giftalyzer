from aiogram.fsm.state import StatesGroup, State


class MarketSearchState(StatesGroup):
    selecting_collection = State()
    selecting_gift = State()
    selecting_backdrop = State()
    confirming_selection = State()
    loading_results = State()
