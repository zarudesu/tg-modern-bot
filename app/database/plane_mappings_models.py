"""
Модели для маппинга Plane пользователей на Telegram пользователей

Заменяет hardcoded PLANE_TO_TELEGRAM_MAP в task_reports_service.py
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, BigInteger, String, Boolean,
    DateTime, Index, UniqueConstraint
)
from sqlalchemy.sql import func

from .database import Base


class PlaneTelegramMapping(Base):
    """
    Маппинг Plane пользователей на Telegram ID

    Позволяет связать разные варианты имён Plane (имя, email, username)
    с конкретным Telegram пользователем.

    Примеры lookup_key:
    - "Zardes" (display name)
    - "Костя Макейкин" (full name in Russian)
    - "zarudesu@gmail.com" (email)
    - "kostya" (username variant)
    """
    __tablename__ = "plane_telegram_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Ключ для поиска (имя в Plane, email, или вариант написания)
    lookup_key = Column(String(255), nullable=False, unique=True, index=True)

    # Telegram данные
    telegram_id = Column(BigInteger, nullable=False, index=True)
    telegram_username = Column(String(255), nullable=True)

    # Метаданные
    display_name = Column(String(255), nullable=True)  # Основное отображаемое имя
    plane_email = Column(String(255), nullable=True)   # Email в Plane (если известен)
    is_active = Column(Boolean, default=True, nullable=False)

    # Аудит
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(String(255), nullable=True)  # Кто создал запись

    __table_args__ = (
        Index("idx_plane_mapping_telegram_id", "telegram_id"),
        Index("idx_plane_mapping_lookup", "lookup_key"),
        Index("idx_plane_mapping_active", "is_active"),
    )

    def __repr__(self):
        return f"<PlaneTelegramMapping(lookup='{self.lookup_key}', tg_id={self.telegram_id})>"


class CompanyMapping(Base):
    """
    Маппинг названий проектов Plane на русские названия компаний

    Заменяет hardcoded COMPANY_MAPPING в task_reports_service.py
    """
    __tablename__ = "company_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Plane данные
    plane_project_name = Column(String(255), nullable=False, unique=True, index=True)
    plane_project_id = Column(String(255), nullable=True)  # UUID проекта в Plane

    # Отображаемое название
    display_name_ru = Column(String(255), nullable=False)  # Русское название
    display_name_en = Column(String(255), nullable=True)   # English name (optional)

    # Дополнительные данные
    client_chat_id = Column(BigInteger, nullable=True)  # Telegram чат клиента (если есть)
    is_active = Column(Boolean, default=True, nullable=False)

    # Аудит
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_company_plane_project", "plane_project_name"),
        Index("idx_company_active", "is_active"),
    )

    def __repr__(self):
        return f"<CompanyMapping(plane='{self.plane_project_name}', ru='{self.display_name_ru}')>"
