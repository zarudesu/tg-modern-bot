"""
Router для Chat Monitor модуля
"""
from aiogram import Router

from .handlers import router as handlers_router
from .message_monitor import router as monitor_router

router = Router()

# Порядок: мониторинг сообщений, затем команды
router.include_router(monitor_router)
router.include_router(handlers_router)
