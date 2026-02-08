from aiogram.fsm.state import State, StatesGroup


class ReconciliationStates(StatesGroup):
    reviewing = State()
    item_review = State()
    journal_prompt = State()
