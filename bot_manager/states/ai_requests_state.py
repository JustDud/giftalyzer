from aiogram.fsm.state import State, StatesGroup


class AIRequestState(StatesGroup):
    selecting_collection = State()
    selecting_gift = State()
    selecting_backdrop = State()
    loading_results = State()
