from aiogram.fsm.state import State, StatesGroup


class AIRequestState(StatesGroup):
    selecting_collection = State()
    entering_link = State()
    selecting_gift = State()
    selecting_backdrop = State()
    loading_results = State()


class AIRequestCollectionAnalysisState(StatesGroup):
    entering_supply = State()
    entering_price = State()
    outputting_results = State()
