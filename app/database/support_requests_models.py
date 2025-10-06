"""
Database models for support requests system
"""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, BigInteger, UniqueConstraint, Index, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .models import Base


class ChatPlaneMapping(Base):
    """Mapping between Telegram chats and Plane projects"""
    __tablename__ = 'chat_plane_mappings'

    id = Column(Integer, primary_key=True)
    chat_id = Column(BigInteger, nullable=False, unique=True, index=True)  # Telegram chat ID
    chat_title = Column(String(255), nullable=True)  # Chat name for reference
    chat_type = Column(String(50), nullable=False)  # group, supergroup, channel

    # Plane project info
    plane_project_id = Column(String(100), nullable=False, index=True)  # Plane project UUID
    plane_project_name = Column(String(255), nullable=True)  # Project name for display

    # Settings
    is_active = Column(Boolean, default=True, index=True)
    allow_all_users = Column(Boolean, default=True)  # Allow all users or only whitelisted

    # Meta
    created_by = Column(BigInteger, nullable=False)  # Admin who created mapping
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    requests = relationship("SupportRequest", back_populates="chat_mapping")

    def __repr__(self):
        return f"<ChatPlaneMapping(chat_id={self.chat_id}, project={self.plane_project_name})>"


class SupportRequest(Base):
    """User support requests submitted through bot"""
    __tablename__ = 'support_requests'

    id = Column(Integer, primary_key=True)

    # Request origin
    chat_id = Column(BigInteger, ForeignKey('chat_plane_mappings.chat_id'), nullable=False, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)  # Telegram user ID
    user_name = Column(String(255), nullable=True)  # User's display name

    # Request details
    title = Column(Text, nullable=False)  # Request title/subject
    description = Column(Text, nullable=True)  # Detailed description
    priority = Column(String(20), nullable=True, default='medium')  # urgent, high, medium, low, none

    # Plane integration
    plane_project_id = Column(String(100), nullable=False, index=True)  # Which project
    plane_issue_id = Column(String(100), nullable=True, index=True)  # Created issue ID
    plane_sequence_id = Column(Integer, nullable=True)  # Issue number (e.g., #123)

    # Status tracking
    status = Column(String(50), nullable=False, default='pending', index=True)  # pending, created, failed, cancelled
    error_message = Column(Text, nullable=True)  # Error if creation failed

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    plane_created_at = Column(DateTime(timezone=True), nullable=True)  # When created in Plane
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    chat_mapping = relationship("ChatPlaneMapping", back_populates="requests")

    __table_args__ = (
        Index('ix_support_requests_user_status', 'user_id', 'status'),
        Index('ix_support_requests_created_at', 'created_at'),
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
    def status_emoji(self) -> str:
        """Emoji for status"""
        status_map = {
            'pending': '⏳',
            'created': '✅',
            'failed': '❌',
            'cancelled': '🚫'
        }
        return status_map.get(self.status.lower(), '❓')

    @property
    def plane_url(self) -> Optional[str]:
        """URL to issue in Plane"""
        if self.plane_project_id and self.plane_issue_id:
            return f"https://plane.hhivp.com/projects/{self.plane_project_id}/issues/{self.plane_issue_id}"
        return None

    def __repr__(self):
        return f"<SupportRequest(id={self.id}, title={self.title[:30]}, status={self.status})>"
