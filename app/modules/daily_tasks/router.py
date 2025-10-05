"""
Роутер модуля ежедневных задач

ПРИОРИТЕТ: ВЫСШИЙ - email от админов обрабатывается ПЕРВЫМ
"""

from aiogram import Router
from .handlers import router as handlers_router
from .email_handlers import router as email_router
from .callback_handlers import router as callback_router
from .navigation_handlers import router as navigation_router

# Создаем основной роутер модуля
router = Router()

# КРИТИЧЕСКИ ВАЖНЫЙ ПОРЯДОК:
# 1. Email обработчик - ПЕРВЫЙ (высший приоритет)
router.include_router(email_router)

# 2. Navigation/Callback обработчики - ВТОРОЙ
router.include_router(navigation_router)
router.include_router(callback_router)

# 3. Команды daily_tasks - ТРЕТИЙ  
router.include_router(handlers_router)
