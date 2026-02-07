"""
Chat AI Models

SQLAlchemy models for AI-powered chat analysis:
- ChatMessage: Persistent message history for context
- ChatAISettings: Per-chat AI configuration
- DetectedIssue: Problem/task tracking
"""

from datetime import datetime, time
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, Float, Boolean,
    DateTime, Time, Index, func
)
from sqlalchemy.orm import relationship
from .models import Base


class ChatMessage(Base):
    """
    Persistent storage for chat messages.
    Used for AI context and analysis.
    """
    __tablename__ = 'chat_messages'

    id = Column(Integer, primary_key=True)
    chat_id = Column(BigInteger, nullable=False, index=True)
    thread_id = Column(BigInteger, nullable=True)  # message_thread_id for topics/threads
    message_id = Column(BigInteger, nullable=True)  # Telegram message ID
    user_id = Column(BigInteger, nullable=False)
    username = Column(String(255), nullable=True)
    display_name = Column(String(255), nullable=True)
    message_text = Column(Text, nullable=True)
    message_type = Column(String(50), default='text')  # text, voice, photo, document
    reply_to_message_id = Column(BigInteger, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # AI analysis fields
    sentiment_score = Column(Float, nullable=True)  # -1.0 (negative) to 1.0 (positive)
    is_question = Column(Boolean, default=False)
    is_answered = Column(Boolean, default=False)
    detected_intent = Column(String(50), nullable=True)  # task, problem, question, info

    # Indexes
    __table_args__ = (
        Index('idx_chat_messages_chat_created', 'chat_id', 'created_at'),
        Index('idx_chat_messages_user', 'user_id'),
        Index('idx_chat_messages_thread', 'thread_id'),
    )

    def __repr__(self):
        return f"<ChatMessage(id={self.id}, chat_id={self.chat_id}, user={self.username})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'chat_id': self.chat_id,
            'thread_id': self.thread_id,
            'message_id': self.message_id,
            'user_id': self.user_id,
            'username': self.username,
            'display_name': self.display_name,
            'message_text': self.message_text,
            'message_type': self.message_type,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'sentiment_score': self.sentiment_score,
            'is_question': self.is_question,
            'detected_intent': self.detected_intent,
        }


class ChatAISettings(Base):
    """
    Per-chat AI configuration.
    Allows customizing AI behavior for each group.
    """
    __tablename__ = 'chat_ai_settings'

    chat_id = Column(BigInteger, primary_key=True)
    chat_title = Column(String(255), nullable=True)

    # Feature toggles
    problem_detection_enabled = Column(Boolean, default=True)
    task_detection_enabled = Column(Boolean, default=True)
    daily_summary_enabled = Column(Boolean, default=False)
    auto_answer_questions = Column(Boolean, default=False)
    notify_task_created = Column(Boolean, default=False)  # Reply in chat when task is created

    # Configuration
    context_size = Column(Integer, default=100)  # Max messages for context
    daily_summary_time = Column(Time, nullable=True)  # e.g., 18:00
    min_confidence_threshold = Column(Float, default=0.7)
    problem_keywords = Column(Text, nullable=True)  # JSON array of custom keywords

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<ChatAISettings(chat_id={self.chat_id}, title={self.chat_title})>"

    def get_problem_keywords(self) -> List[str]:
        """Parse problem_keywords JSON"""
        if not self.problem_keywords:
            return []
        import json
        try:
            return json.loads(self.problem_keywords)
        except:
            return []

    def set_problem_keywords(self, keywords: List[str]):
        """Set problem_keywords as JSON"""
        import json
        self.problem_keywords = json.dumps(keywords, ensure_ascii=False)


class DetectedIssue(Base):
    """
    Tracking detected problems and tasks.
    Records AI-detected issues for follow-up.
    """
    __tablename__ = 'detected_issues'

    id = Column(Integer, primary_key=True)
    chat_id = Column(BigInteger, nullable=False, index=True)
    message_id = Column(BigInteger, nullable=True)
    user_id = Column(BigInteger, nullable=True)

    # Issue details
    issue_type = Column(String(50), nullable=False)  # problem, unanswered, urgent, task
    confidence = Column(Float, nullable=True)
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    original_text = Column(Text, nullable=True)

    # Status tracking
    status = Column(String(50), default='new')  # new, notified, acknowledged, resolved, ignored
    notified_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(BigInteger, nullable=True)

    # Plane integration
    plane_issue_id = Column(String(100), nullable=True)
    plane_project_id = Column(String(100), nullable=True)

    # Deduplication
    content_hash = Column(String(16), nullable=True, index=True)

    # Training data fields
    ai_response_json = Column(Text, nullable=True)          # Raw AI response
    ai_model_used = Column(String(100), nullable=True)       # Model name
    user_feedback = Column(String(50), nullable=True)        # accepted/rejected/corrected/duplicate_comment
    user_edited_title = Column(String(255), nullable=True)
    user_edited_desc = Column(Text, nullable=True)
    user_assigned_to = Column(String(255), nullable=True)    # Assignee display name
    feedback_at = Column(DateTime(timezone=True), nullable=True)
    correction_distance = Column(Float, nullable=True)       # 0.0-1.0 edit distance

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Indexes
    __table_args__ = (
        Index('idx_detected_issues_chat_status', 'chat_id', 'status'),
        Index('idx_detected_issues_type', 'issue_type'),
    )

    def __repr__(self):
        return f"<DetectedIssue(id={self.id}, type={self.issue_type}, status={self.status})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'chat_id': self.chat_id,
            'message_id': self.message_id,
            'issue_type': self.issue_type,
            'confidence': self.confidence,
            'title': self.title,
            'description': self.description,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'plane_issue_id': self.plane_issue_id,
        }


class ThreadClientMapping(Base):
    """
    Maps threads in admin work group to client chats.

    Use case:
    - Admin work group has threads for each client (e.g., "DELTA", "HARZL")
    - Each thread is linked to the actual client chat
    - /ai_summary in thread shows summary FROM client chat
    """
    __tablename__ = 'thread_client_mappings'

    id = Column(Integer, primary_key=True)

    # Thread in admin work group
    work_group_id = Column(BigInteger, nullable=False)  # Admin work group chat_id
    thread_id = Column(BigInteger, nullable=False)  # Thread ID in work group
    thread_name = Column(String(255), nullable=True)  # Thread name for display

    # Client chat to monitor
    client_chat_id = Column(BigInteger, nullable=False)  # Client's group chat_id
    client_name = Column(String(255), nullable=False)  # Client name (e.g., "DELTA")

    # Optional Plane integration
    plane_project_id = Column(String(100), nullable=True)

    # Status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(BigInteger, nullable=True)  # Admin who created mapping

    # Indexes
    __table_args__ = (
        Index('idx_thread_mapping_work_group', 'work_group_id'),
        Index('idx_thread_mapping_thread', 'thread_id'),
        Index('idx_thread_mapping_client', 'client_chat_id'),
        Index('idx_thread_mapping_unique', 'work_group_id', 'thread_id', unique=True),
    )

    def __repr__(self):
        return f"<ThreadClientMapping(thread={self.thread_id}, client={self.client_name})>"

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'work_group_id': self.work_group_id,
            'thread_id': self.thread_id,
            'thread_name': self.thread_name,
            'client_chat_id': self.client_chat_id,
            'client_name': self.client_name,
            'plane_project_id': self.plane_project_id,
            'is_active': self.is_active,
        }
