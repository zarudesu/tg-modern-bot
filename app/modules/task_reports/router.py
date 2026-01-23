"""
Task Reports Module Router

Combines all task_reports handlers into a single router
"""

from aiogram import Router
from .handlers import (
    creation_router,
    preview_router,
    edit_router,
    approval_router,
    ai_generation_router,
)
from .metadata import (
    duration_router,
    travel_router,
    company_router,
    workers_router,
    navigation_router,
)


# Main router for task_reports module
router = Router(name="task_reports")

# Include sub-routers in priority order
# 1. Metadata handlers FIRST (for FSM state-specific handlers)
router.include_router(duration_router)      # Duration selection
router.include_router(travel_router)        # Work type (travel/remote)
router.include_router(company_router)       # Company selection
router.include_router(workers_router)       # Workers multi-select
router.include_router(navigation_router)    # Back buttons and field editing

# 2. Main handlers (grouped by functionality)
router.include_router(creation_router)      # Report creation flow
router.include_router(preview_router)       # Report preview
router.include_router(edit_router)          # Report editing
router.include_router(approval_router)      # Approval, sending, rejection
router.include_router(ai_generation_router) # AI-powered report generation
