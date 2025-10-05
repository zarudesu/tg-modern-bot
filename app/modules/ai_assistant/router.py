"""
Router для AI Assistant модуля
"""
from aiogram import Router

from .handlers import router as handlers_router
from .ai_handlers import router as ai_router

router = Router()

# Порядок важен: сначала AI обработчики, потом команды
router.include_router(ai_router)
router.include_router(handlers_router)
