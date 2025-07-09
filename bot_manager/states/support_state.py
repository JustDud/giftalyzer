from aiogram.fsm.state import StatesGroup, State

class SupportState(StatesGroup):
    waiting_for_description = State()