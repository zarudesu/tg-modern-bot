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

    # Metadata collection workflow
    filling_duration = State()  # Waiting for work duration (e.g., "2h")
    filling_work_type = State()  # Waiting for work type selection (travel/remote)
    filling_company = State()  # Waiting for company name
    filling_workers = State()  # Waiting for workers list
