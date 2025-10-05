"""
Кастомные фильтры для модуля журнала работ
"""

from aiogram.filters import BaseFilter
from aiogram.types import Message
from typing import Any

from ...database.database import get_async_session
from ...services.work_journal_service import WorkJournalService
from ...utils.logger import bot_logger


class IsWorkJournalActiveFilter(BaseFilter):
    """
    Фильтр для проверки активного состояния work_journal
    
    Возвращает True только если:
    1. У пользователя есть состояние work_journal
    2. Состояние НЕ равно 'idle' (idle = неактивное состояние)
    3. Состояние НЕ равно None
    """
    
    async def __call__(self, message: Message) -> bool:
        try:
            user_id = message.from_user.id
            
            # Проверяем состояние пользователя
            async for session in get_async_session():
                service = WorkJournalService(session)
                user_state = await service.get_user_state(user_id)
                
                # Нет состояния = не активен
                if not user_state or not user_state.current_state:
                    return False
                
                # idle = не активное состояние для work_journal
                if user_state.current_state == "idle":
                    return False
                
                # Логируем активное состояние
                bot_logger.info(f"Work journal ACTIVE state for user {user_id}: {user_state.current_state}")
                return True
                
        except Exception as e:
            bot_logger.error(f"Error checking work_journal state for user {user_id}: {e}")
            return False
        
        return False


class IsWorkJournalIdleFilter(BaseFilter):
    """
    Фильтр для проверки неактивного состояния work_journal
    
    Возвращает True если:
    1. У пользователя нет состояния work_journal  
    2. Состояние равно 'idle'
    3. Состояние равно None
    """
    
    async def __call__(self, message: Message) -> bool:
        try:
            user_id = message.from_user.id
            
            async for session in get_async_session():
                service = WorkJournalService(session)
                user_state = await service.get_user_state(user_id)
                
                # Нет состояния = idle
                if not user_state or not user_state.current_state:
                    return True
                
                # idle = неактивное состояние  
                if user_state.current_state == "idle":
                    return True
                
                # Любое другое состояние = активен
                return False
                
        except Exception as e:
            bot_logger.error(f"Error checking work_journal idle state for user {user_id}: {e}")
            return True  # По умолчанию считаем idle
        
        return True
