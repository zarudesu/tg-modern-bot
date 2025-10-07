"""
Task Reports Module Router

Combines all task_reports handlers into a single router
"""

from aiogram import Router
from .handlers import router as handlers_router


# Main router for task_reports module
router = Router(name="task_reports")

# Include sub-routers in priority order
router.include_router(handlers_router)
