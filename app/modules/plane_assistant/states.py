"""FSM states for /plane assistant."""

from aiogram.fsm.state import State, StatesGroup


class PlaneAssistantStates(StatesGroup):
    conversation = State()
    confirm_write = State()
    drafting_task = State()
