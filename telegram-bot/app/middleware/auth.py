"""
Middleware для аутентификации и авторизации
"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..database.database import get_async_session
from ..database.models import BotUser
from ..utils.logger import bot_logger, log_user_action
from ..config import settings


class AuthMiddleware(BaseMiddleware):
    """Middleware для проверки прав доступа пользователей"""
    
    def __init__(self):
        super().__init__()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Основная логика middleware"""
        
        # Проверяем тип события
        if not isinstance(event, (Message, CallbackQuery)):
            return await handler(event, data)
        
        # Получаем пользователя
        user = event.from_user
        if not user:
            bot_logger.warning("Event without user received")
            return await handler(event, data)
        
        # Проверяем заблокированных пользователей
        if user.id in getattr(settings, 'blocked_users', []):
            bot_logger.warning(f"Blocked user {user.id} tried to use bot")
            return
        
        # Получаем информацию о пользователе из базы
        try:
            async for session in get_async_session():
                result = await session.execute(
                    select(BotUser).where(BotUser.telegram_user_id == user.id)
                )
                db_user = result.scalar_one_or_none()
                
                # Добавляем информацию о пользователе в данные
                data['db_user'] = db_user
                data['user_role'] = db_user.role if db_user else 'guest'
                data['is_admin'] = db_user.role == 'admin' if db_user else False
                
                # Проверяем активность пользователя
                if db_user and not db_user.is_active:
                    bot_logger.warning(f"Inactive user {user.id} tried to use bot")
                    if isinstance(event, Message):
                        await event.answer(
                            "🚫 Ваш аккаунт деактивирован\\. Обратитесь к администратору\\.",
                            parse_mode="MarkdownV2"
                        )
                    return
                
                return await handler(event, data)
                
        except Exception as e:
            bot_logger.error(f"Auth middleware error: {e}")
            return await handler(event, data)


class RoleCheckMiddleware(BaseMiddleware):
    """Middleware для проверки ролей пользователей"""
    
    def __init__(self, required_role: str = None):
        super().__init__()
        self.required_role = required_role
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Проверка роли пользователя"""
        
        if not self.required_role:
            return await handler(event, data)
        
        user_role = data.get('user_role', 'guest')
        
        # Иерархия ролей: admin > user > guest
        role_hierarchy = {
            'guest': 0,
            'user': 1,
            'admin': 2
        }
        
        required_level = role_hierarchy.get(self.required_role, 0)
        user_level = role_hierarchy.get(user_role, 0)
        
        if user_level < required_level:
            bot_logger.warning(
                f"User {event.from_user.id} with role {user_role} "
                f"tried to access {self.required_role} function"
            )
            
            if isinstance(event, Message):
                await event.answer(
                    "🔒 Недостаточно прав для выполнения этой операции\\.",
                    parse_mode="MarkdownV2"
                )
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    "Недостаточно прав для выполнения операции",
                    show_alert=True
                )
            return
        
        return await handler(event, data)


def admin_required(handler):
    """Декоратор для команд, требующих права администратора"""
    async def wrapper(event, *args, **kwargs):
        if not kwargs.get('is_admin', False):
            if isinstance(event, Message):
                await event.answer(
                    "🔒 Эта команда доступна только администраторам\\.",
                    parse_mode="MarkdownV2"
                )
            return
        return await handler(event, *args, **kwargs)
    return wrapper


def user_required(handler):
    """Декоратор для команд, требующих минимальную роль user"""
    async def wrapper(event, *args, **kwargs):
        user_role = kwargs.get('user_role', 'guest')
        if user_role == 'guest':
            if isinstance(event, Message):
                await event.answer(
                    "🔒 Для использования этой команды требуется регистрация\\. "
                    "Обратитесь к администратору\\.",
                    parse_mode="MarkdownV2"
                )
            return
        return await handler(event, *args, **kwargs)
    return wrapper
