"""FSM states for editing AI-detected tasks before creation."""

from aiogram.fsm.state import State, StatesGroup


class AIEditTaskStates(StatesGroup):
    editing_title = State()
    editing_description = State()
    confirming = State()
