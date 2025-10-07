"""
Task Reports Module - Automated client reporting for completed tasks

When a task is marked as Done in Plane:
1. n8n webhook triggers bot
2. Bot creates TaskReport (pending)
3. Admin fills report (FSM workflow)
4. Report sent to client in chat
"""

from .router import router as task_reports_router
from .states import TaskReportStates

__all__ = [
    'task_reports_router',
    'TaskReportStates'
]
