"""
FSM States for Chat Support module
"""
from aiogram.fsm.state import State, StatesGroup


class SupportRequestStates(StatesGroup):
    """States for support request creation flow"""
    waiting_for_problem = State()  # User is waiting to input problem description
