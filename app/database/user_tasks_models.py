"""
Database models for user tasks caching system
"""

from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, BigInteger, UniqueConstraint, Index
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

from .models import Base


class UserTasksCache(Base):
    """Cached tasks for users from Plane.so API"""
    __tablename__ = 'user_tasks_cache'
    
    id = Column(Integer, primary_key=True)
    user_email = Column(String(255), nullable=False)
    plane_task_id = Column(String(100), nullable=False)  # Plane task UUID
    plane_project_id = Column(String(100), nullable=False)  # Plane project UUID
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), nullable=False)  # e.g. 'todo', 'in_progress', 'done'
    priority = Column(String(20), nullable=True, default='none')  # 'urgent', 'high', 'medium', 'low', 'none'
    project_name = Column(String(255), nullable=True)
    assignee_name = Column(String(255), nullable=True)
    assignee_email = Column(String(255), nullable=True)
    state_name = Column(String(100), nullable=True)  # Plane state name
    sequence_id = Column(Integer, nullable=True)  # Plane sequence ID (e.g., #123)
    due_date = Column(DateTime(timezone=True), nullable=True)
    plane_created_at = Column(DateTime(timezone=True), nullable=True)
    plane_updated_at = Column(DateTime(timezone=True), nullable=True)
    is_overdue = Column(Boolean, default=False)
    is_due_today = Column(Boolean, default=False)
    cached_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        UniqueConstraint('user_email', 'plane_task_id', name='uq_user_email_task_id'),
        Index('ix_user_tasks_cache_user_email', 'user_email'),
        Index('ix_user_tasks_cache_status', 'status'),
        Index('ix_user_tasks_cache_priority', 'priority'),
        Index('ix_user_tasks_cache_due_date', 'due_date'),
        Index('ix_user_tasks_cache_updated_at', 'updated_at'),
    )
    
    @property
    def priority_emoji(self) -> str:
        """Emoji for priority level"""
        priority_map = {
            'urgent': '🔴',
            'high': '🟠', 
            'medium': '🟡',
            'low': '🟢',
            'none': '⚪'
        }
        return priority_map.get((self.priority or 'none').lower(), '⚪')
    
    @property
    def priority_order(self) -> int:
        """Priority order for sorting (lower = higher priority)"""
        priority_order_map = {
            'urgent': 0,
            'high': 1,
            'medium': 2,
            'low': 3,
            'none': 4
        }
        return priority_order_map.get((self.priority or 'none').lower(), 4)
    
    @property
    def state_emoji(self) -> str:
        """Emoji for state"""
        state_map = {
            'backlog': '📋',
            'todo': '📝',
            'in_progress': '⚡',
            'in progress': '⚡',
            'in_review': '👀',
            'in review': '👀',
            'done': '✅',
            'completed': '✅',
            'cancelled': '❌',
            'canceled': '❌'
        }
        state_name = (self.state_name or '').lower()
        return state_map.get(state_name, '📋')

    @property
    def task_url(self) -> str:
        """URL to task in Plane"""
        return f"https://plane.hhivp.com/projects/{self.plane_project_id}/issues/{self.plane_task_id}"


class UserTasksSyncStatus(Base):
    """Tracking sync status for each user"""
    __tablename__ = 'user_tasks_sync_status'
    
    id = Column(Integer, primary_key=True)
    user_email = Column(String(255), nullable=False, unique=True, index=True)
    telegram_user_id = Column(BigInteger, nullable=True, index=True)
    last_sync_started = Column(DateTime(timezone=True), nullable=True)
    last_sync_completed = Column(DateTime(timezone=True), nullable=True)
    last_sync_error = Column(Text, nullable=True)
    sync_in_progress = Column(Boolean, default=False)
    total_tasks_found = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    @property
    def sync_status_text(self) -> str:
        """Human-readable sync status"""
        if self.sync_in_progress:
            return "⏳ Синхронизация в процессе..."
        elif self.last_sync_error:
            return f"❌ Ошибка: {self.last_sync_error[:100]}"
        elif self.last_sync_completed:
            return f"✅ Обновлено: {self.last_sync_completed.strftime('%H:%M %d.%m')}"
        else:
            return "🆕 Еще не синхронизировано"
    
    @property
    def needs_sync(self) -> bool:
        """Check if sync is needed (>30 minutes since last sync)"""
        if self.sync_in_progress:
            return False
        if not self.last_sync_completed:
            return True
        
        now = datetime.now(timezone.utc)
        time_diff = now - self.last_sync_completed
        return time_diff.total_seconds() > 1800  # 30 minutes