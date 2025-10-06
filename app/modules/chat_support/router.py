"""
Chat Support Router - Simple and clear
"""
from aiogram import Router
from . import handlers, admin_handlers


# Main router
router = Router(name="chat_support")

# Priority: admin first, then user handlers
router.include_router(admin_handlers.router)
router.include_router(handlers.router)
