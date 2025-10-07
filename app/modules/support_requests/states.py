"""
FSM States for Support Request creation
"""

from aiogram.fsm.state import State, StatesGroup


class SupportRequestStates(StatesGroup):
    """States for creating a support request"""
    waiting_for_title = State()  # Waiting for request title
    waiting_for_description = State()  # Waiting for detailed description
    waiting_for_priority = State()  # Waiting for priority selection (optional)
    confirming = State()  # Confirming before submission
