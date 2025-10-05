"""
Work Journal Module - Основной роутер
"""
from aiogram import Router
from . import commands, callbacks, text_handlers

# Создаем основной роутер модуля
router = Router()

# Подключаем все подмодули
router.include_router(commands.router)
router.include_router(callbacks.router) 
router.include_router(text_handlers.router)
