"""
Модели базы данных для модуля журнала работ
"""
from datetime import datetime, date
from typing import Optional
from sqlalchemy import (
    Column, Integer, BigInteger, String, Boolean, 
    Text, DateTime, Date, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .models import Base


class WorkJournalEntry(Base):
    """Модель записи в журнале работ"""
    __tablename__ = "work_journal_entries"
    
    # Основные поля
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id = Column(BigInteger, ForeignKey("bot_users.telegram_user_id"), nullable=False)
    user_email = Column(String(255), nullable=False)
    
    # Данные о работе
    work_date = Column(Date, nullable=False)
    company = Column(String(255), nullable=False)
    work_duration = Column(String(50), nullable=False)
    work_description = Column(Text, nullable=False)
    is_travel = Column(Boolean, nullable=False, default=False)
    worker_names = Column(Text, nullable=False)  # JSON массив исполнителей
    
    # Кто создал запись
    created_by_user_id = Column(BigInteger, ForeignKey("bot_users.telegram_user_id"), nullable=False)
    created_by_name = Column(String(255), nullable=False)  # Имя создателя записи
    
    # Метки времени
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Статус синхронизации с n8n
    n8n_sync_status = Column(String(50), default='pending', nullable=False)  # pending, success, failed
    n8n_sync_attempts = Column(Integer, default=0, nullable=False)
    n8n_last_sync_at = Column(DateTime, nullable=True)
    n8n_error_message = Column(Text, nullable=True)
    
    # Связи (без back_populates для избежания циклических зависимостей)
    user = relationship("BotUser", foreign_keys=[telegram_user_id])
    created_by = relationship("BotUser", foreign_keys=[created_by_user_id])
    
    # Индексы для оптимизации запросов
    __table_args__ = (
        Index("idx_work_journal_user_id", "telegram_user_id"),
        Index("idx_work_journal_date", "work_date"),
        Index("idx_work_journal_company", "company"),
        Index("idx_work_journal_sync_status", "n8n_sync_status"),
        Index("idx_work_journal_created_at", "created_at"),
        Index("idx_work_journal_date_user", "work_date", "telegram_user_id"),  # Составной индекс
        Index("idx_work_journal_created_by", "created_by_user_id"),  # Новый индекс для создателя
    )
    
    def __repr__(self):
        return (f"<WorkJournalEntry(id={self.id}, user_id={self.telegram_user_id}, "
                f"date={self.work_date}, company='{self.company}', "
                f"created_by={self.created_by_name})>")


class UserWorkJournalState(Base):
    """Модель состояния пользователя при заполнении журнала работ"""
    __tablename__ = "user_work_journal_states"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id = Column(BigInteger, ForeignKey("bot_users.telegram_user_id"), nullable=False, unique=True)
    
    # Текущее состояние заполнения
    current_state = Column(String(50), default='idle', nullable=False)
    
    # Данные текущей записи (в JSON формате через session_data)
    draft_date = Column(Date, nullable=True)
    draft_company = Column(String(255), nullable=True)
    draft_duration = Column(String(50), nullable=True)
    draft_description = Column(Text, nullable=True)
    draft_is_travel = Column(Boolean, nullable=True)
    draft_workers = Column(Text, nullable=True)  # JSON массив выбранных исполнителей
    
    # Контекст и вспомогательные данные
    message_to_edit = Column(Integer, nullable=True)  # ID сообщения для редактирования
    additional_data = Column(Text, nullable=True)     # Дополнительные данные в JSON
    
    # Метки времени
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Связи
    user = relationship("BotUser")
    
    # Индексы
    __table_args__ = (
        Index("idx_user_state_telegram_id", "telegram_user_id"),
        Index("idx_user_state_current", "current_state"),
    )
    
    def __repr__(self):
        return (f"<UserWorkJournalState(user_id={self.telegram_user_id}, "
                f"state='{self.current_state}')>")


class WorkJournalCompany(Base):
    """Модель предустановленных компаний"""
    __tablename__ = "work_journal_companies"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    display_order = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Индексы
    __table_args__ = (
        Index("idx_company_name", "name"),
        Index("idx_company_active", "is_active"),
        Index("idx_company_order", "display_order"),
    )
    
    def __repr__(self):
        return f"<WorkJournalCompany(id={self.id}, name='{self.name}')>"


class WorkJournalWorker(Base):
    """Модель предустановленных исполнителей"""
    __tablename__ = "work_journal_workers"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    telegram_username = Column(String(255), nullable=True)  # Без @
    telegram_user_id = Column(BigInteger, nullable=True)
    plane_user_names = Column(Text, nullable=True)  # JSON массив имен пользователя в Plane
    mention_enabled = Column(Boolean, default=True, nullable=False)
    display_order = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Индексы
    __table_args__ = (
        Index("idx_worker_name", "name"),
        Index("idx_worker_active", "is_active"),
        Index("idx_worker_order", "display_order"),
        Index("idx_worker_telegram_username", "telegram_username"),
        Index("idx_worker_telegram_user_id", "telegram_user_id"),
    )
    
    def __repr__(self):
        mention = f"@{self.telegram_username}" if self.telegram_username else "no mention"
        return f"<WorkJournalWorker(id={self.id}, name='{self.name}', {mention})>"


class UserNotificationPreferences(Base):
    """Модель настроек уведомлений пользователей"""
    __tablename__ = "user_notification_preferences"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id = Column(BigInteger, ForeignKey("bot_users.telegram_user_id"), nullable=False, unique=True)
    
    # Настройки уведомлений
    enable_work_assignment_notifications = Column(Boolean, default=False, nullable=False)  # Уведомления в ЛС
    enable_mentions_in_chat = Column(Boolean, default=True, nullable=False)  # Упоминания в чате
    
    # Метки времени
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Связи
    user = relationship("BotUser")
    
    # Индексы
    __table_args__ = (
        Index("idx_notification_prefs_user_id", "telegram_user_id"),
    )
    
    def __repr__(self):
        return f"<UserNotificationPreferences(user_id={self.telegram_user_id}, dm={self.enable_work_assignment_notifications})>"
