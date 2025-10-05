"""
Кастомные фильтры для модуля ежедневных задач
"""

from aiogram.filters import BaseFilter
from aiogram.types import Message
from typing import Any
import re

from ...config import settings
from ...utils.logger import bot_logger


class IsEmailFilter(BaseFilter):
    """Фильтр для проверки, что сообщение является email"""
    
    def __init__(self):
        self.email_regex = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    
    async def __call__(self, message: Message) -> bool:
        if not message.text:
            return False
        
        text = message.text.strip()
        is_email = bool(self.email_regex.match(text))
        
        if is_email:
            bot_logger.info(f"Email detected: {text} from user {message.from_user.id}")
        
        return is_email


class IsAdminFilter(BaseFilter):
    """Фильтр для проверки, что пользователь является админом"""
    
    async def __call__(self, message: Message) -> bool:
        user_id = message.from_user.id
        is_admin = user_id in settings.admin_user_id_list
        
        if not is_admin:
            bot_logger.info(f"Non-admin user {user_id} tried to access admin function")
        
        return is_admin


class IsAdminEmailFilter(BaseFilter):
    """Комбинированный фильтр: email от админа"""
    
    def __init__(self):
        self.email_filter = IsEmailFilter()
        self.admin_filter = IsAdminFilter()
    
    async def __call__(self, message: Message) -> bool:
        is_email = await self.email_filter(message)
        is_admin = await self.admin_filter(message)
        
        result = is_email and is_admin
        
        if result:
            bot_logger.info(f"ADMIN EMAIL DETECTED: {message.text} from admin {message.from_user.id}")
        
        return result
