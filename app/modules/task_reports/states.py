"""
Task Reports FSM States

States for task report filling workflow:
1. Admin receives notification about closed task
2. Admin enters state to fill report
3. Admin reviews report
4. Report sent to client
"""

from aiogram.fsm.state import State, StatesGroup


class TaskReportStates(StatesGroup):
    """States for task report workflow"""

    # Admin is filling/editing report text
    filling_report = State()

    # Admin is reviewing report before sending to client
    reviewing_report = State()
