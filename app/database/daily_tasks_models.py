"""
Модели для ежедневных задач и настроек админов
"""
from datetime import datetime, time
from typing import Optional, Dict, Any
from sqlalchemy import (
    Column, Integer, BigInteger, String, Boolean, 
    Text, DateTime, JSON, Time
)
from sqlalchemy.sql import func

from .models import Base


class AdminDailyTasksSettings(Base):
    """Настройки ежедневных задач для админов"""
    __tablename__ = "admin_daily_tasks_settings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id = Column(BigInteger, unique=True, nullable=False)
    
    # Основные настройки
    enabled = Column(Boolean, default=False, nullable=False)
    notification_time = Column(Time, default=time(9, 0), nullable=False)  # 09:00
    timezone = Column(String(50), default="Europe/Moscow", nullable=False)
    
    # Настройки содержимого
    include_overdue = Column(Boolean, default=True, nullable=False)
    include_today = Column(Boolean, default=True, nullable=False)  
    include_upcoming = Column(Boolean, default=True, nullable=False)
    group_by_project = Column(Boolean, default=True, nullable=False)
    
    # Дополнительные настройки
    max_tasks_per_section = Column(Integer, default=5, nullable=False)
    plane_email = Column(String(255), nullable=True)  # Email в Plane для сопоставления
    
    # Метаданные
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    last_sent_at = Column(DateTime, nullable=True)  # Время последней отправки
    
    def __repr__(self):
        return f"<AdminDailyTasksSettings(user_id={self.telegram_user_id}, enabled={self.enabled})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь"""
        return {
            'enabled': self.enabled,
            'notification_time': self.notification_time.strftime('%H:%M') if self.notification_time else '09:00',
            'time': self.notification_time.strftime('%H:%M') if self.notification_time else '09:00',  # Для обратной совместимости
            'timezone': self.timezone,
            'include_overdue': self.include_overdue,
            'include_today': self.include_today,
            'include_upcoming': self.include_upcoming,
            'group_by_project': self.group_by_project,
            'max_tasks_per_section': self.max_tasks_per_section,
            'plane_email': self.plane_email,
            'last_sent_at': self.last_sent_at.isoformat() if self.last_sent_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], telegram_user_id: int):
        """Создать из словаря"""
        # Парсим время
        time_str = data.get('time', '09:00')
        try:
            hour, minute = map(int, time_str.split(':'))
            notification_time = time(hour, minute)
        except:
            notification_time = time(9, 0)
        
        return cls(
            telegram_user_id=telegram_user_id,
            enabled=data.get('enabled', False),
            notification_time=notification_time,
            timezone=data.get('timezone', 'Europe/Moscow'),
            include_overdue=data.get('include_overdue', True),
            include_today=data.get('include_today', True),
            include_upcoming=data.get('include_upcoming', True),
            group_by_project=data.get('group_by_project', True),
            max_tasks_per_section=data.get('max_tasks_per_section', 5),
            plane_email=data.get('plane_email')
        )


class DailyTasksLog(Base):
    """Лог отправки ежедневных задач"""
    __tablename__ = "daily_tasks_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id = Column(BigInteger, nullable=False)
    
    # Данные отправки
    sent_at = Column(DateTime, default=func.now(), nullable=False)
    success = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)
    
    # Статистика задач
    total_tasks = Column(Integer, default=0, nullable=False)
    overdue_tasks = Column(Integer, default=0, nullable=False)
    today_tasks = Column(Integer, default=0, nullable=False)
    upcoming_tasks = Column(Integer, default=0, nullable=False)
    
    # Дополнительные данные
    plane_response_time = Column(Integer, nullable=True)  # Время ответа Plane API в мс
    tasks_data = Column(JSON, nullable=True)  # Данные о задачах для анализа
    
    def __repr__(self):
        return f"<DailyTasksLog(user_id={self.telegram_user_id}, success={self.success}, sent_at={self.sent_at})>"
