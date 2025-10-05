"""
Роутер модуля журнала работ

ПРИОРИТЕТ: НИЗКИЙ - обрабатывается после daily_tasks
Текстовые сообщения обрабатываются только при активных состояниях
"""

from aiogram import Router
from .handlers import router as handlers_router
from .text_handlers import router as text_router
from .callback_handlers import router as callback_router

# Создаем основной роутер модуля
router = Router()

# ПОРЯДОК РОУТЕРОВ:
# 1. Команды work_journal - ПЕРВЫЙ
router.include_router(handlers_router)

# 2. Callback обработчики - ВТОРОЙ  
router.include_router(callback_router)

# 3. Текстовые обработчики с фильтрами состояний - ПОСЛЕДНИЙ
router.include_router(text_router)
