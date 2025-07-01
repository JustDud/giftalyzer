from aiogram.fsm.state import StatesGroup, State


class GiftStates(StatesGroup):
    WaitingForGiftID = State()
    WaitingForManualInput = State()
    WaitingForAIQuestion = State()
    WaitingForHelpInput = State()