"""
Support Requests Router - combines all handlers
"""

from aiogram import Router
from . import handlers_new as handlers, admin_handlers


# Create main router for support requests module
router = Router(name="support_requests")

# Include sub-routers in priority order
# 1. Admin handlers (highest priority - for admin commands)
router.include_router(admin_handlers.router)

# 2. User handlers (regular user commands and FSM)
router.include_router(handlers.router)
