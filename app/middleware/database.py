"""
Database Session Middleware - управление сессиями базы данных
"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from ..database.database import get_async_session
from ..utils.logger import bot_logger


class DatabaseSessionMiddleware(BaseMiddleware):
    """Middleware для управления сессиями базы данных"""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Создает одну сессию для всего request lifecycle"""
        
        # Проверяем, не создана ли уже сессия
        if 'db_session' in data:
            return await handler(event, data)
        
        async for session in get_async_session():
            try:
                # Добавляем сессию в data для использования в других middleware и handlers
                data['db_session'] = session
                
                # Вызываем следующий middleware/handler
                result = await handler(event, data)
                
                # Если все прошло успешно, коммитим транзакцию
                await session.commit()
                return result
                
            except Exception as e:
                # В случае ошибки, откатываем транзакцию
                await session.rollback()
                bot_logger.error(f"Database session error: {e}")
                raise
            finally:
                # Сессия закроется автоматически благодаря async context manager
                pass
