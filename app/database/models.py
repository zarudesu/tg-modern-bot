"""
Модели базы данных для Telegram бота
"""
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import (
    Column, Integer, BigInteger, String, Boolean, 
    Text, DateTime, JSON, ForeignKey, Float, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class BotUser(Base):
    """Модель пользователя бота"""
    __tablename__ = "bot_users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    role = Column(String(50), default="guest", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    language_code = Column(String(10), default="ru", nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    last_seen = Column(DateTime, default=func.now(), nullable=False)
    settings = Column(JSON, default=dict, nullable=False)
    
    # Связи
    message_logs = relationship("MessageLog", back_populates="user")
    sessions = relationship("UserSession", back_populates="user")
    # work_journal_entries связь вынесена в work_journal_models.py для избежания циклических импортов
    
    # Индексы
    __table_args__ = (
        Index("idx_telegram_user_id", "telegram_user_id"),
        Index("idx_role", "role"),
        Index("idx_is_active", "is_active"),
    )
    
    def __repr__(self):
        return f"<BotUser(id={self.id}, telegram_id={self.telegram_user_id}, username={self.username})>"


class MessageLog(Base):
    """Модель логов сообщений"""
    __tablename__ = "message_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_message_id = Column(String(50), nullable=False)
    telegram_user_id = Column(BigInteger, ForeignKey("bot_users.telegram_user_id"), nullable=False)
    chat_id = Column(BigInteger, nullable=False)
    chat_type = Column(String(50), nullable=False)  # private, group, supergroup
    message_type = Column(String(50), nullable=False)  # text, photo, document, etc.
    text_content = Column(Text, nullable=True)
    message_metadata = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Связи
    user = relationship("BotUser", back_populates="message_logs")
    
    # Индексы
    __table_args__ = (
        Index("idx_telegram_user_id_log", "telegram_user_id"),
        Index("idx_chat_id", "chat_id"),
        Index("idx_created_at", "created_at"),
        Index("idx_message_type", "message_type"),
    )
    
    def __repr__(self):
        return f"<MessageLog(id={self.id}, user_id={self.telegram_user_id}, chat_id={self.chat_id})>"


class UserSession(Base):
    """Модель пользовательских сессий"""
    __tablename__ = "user_sessions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id = Column(BigInteger, ForeignKey("bot_users.telegram_user_id"), nullable=False)
    session_data = Column(JSON, default=dict, nullable=False)
    last_command = Column(String(255), nullable=True)
    context = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Связи
    user = relationship("BotUser", back_populates="sessions")
    
    # Индексы
    __table_args__ = (
        Index("idx_telegram_user_id_session", "telegram_user_id"),
        Index("idx_updated_at", "updated_at"),
    )
    
    def __repr__(self):
        return f"<UserSession(id={self.id}, user_id={self.telegram_user_id}, command={self.last_command})>"


class APILog(Base):
    """Модель логов API запросов"""
    __tablename__ = "api_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    service_name = Column(String(100), nullable=False)
    endpoint = Column(String(500), nullable=False)
    method = Column(String(10), nullable=False)
    request_data = Column(JSON, nullable=True)
    response_status = Column(Integer, nullable=True)
    response_data = Column(JSON, nullable=True)
    execution_time = Column(Float, nullable=True)
    telegram_user_id = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Индексы
    __table_args__ = (
        Index("idx_service_name", "service_name"),
        Index("idx_created_at_api", "created_at"),
        Index("idx_response_status", "response_status"),
        Index("idx_execution_time", "execution_time"),
    )
    
    def __repr__(self):
        return f"<APILog(id={self.id}, service={self.service_name}, endpoint={self.endpoint})>"
