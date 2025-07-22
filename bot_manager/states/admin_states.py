from aiogram.fsm.state import StatesGroup, State


class RefundFSM(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_transaction_id = State()


# New FSM for checking subscriptions
class CheckSubsFSM(StatesGroup):
    waiting_for_user_id = State()


class PromoStatsFSM(StatesGroup):
    waiting_for_promo_code = State()


class PromoAddFSM(StatesGroup):
    waiting_for_code = State()
    waiting_for_owner_id = State()
    waiting_for_discount = State()
    waiting_for_profit = State()
    waiting_for_single_use = State()


class PromoDeleteFSM(StatesGroup):
    waiting_for_code = State()


class PromoApplyFSM(StatesGroup):
    waiting_for_promo_code = State()
