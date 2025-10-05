"""
Конкретные типы событий для бота

Все события наследуются от базового Event и добавляют специфичные поля
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
from aiogram.types import Message, CallbackQuery, ChatMemberUpdated

from .event_bus import Event, EventPriority


# ========== TELEGRAM СОБЫТИЯ ==========

@dataclass
class MessageReceivedEvent(Event):
    """Событие получения сообщения"""

    def __init__(
        self,
        message: Message,
        user_id: int,
        chat_id: int,
        text: Optional[str] = None,
        message_type: str = "text",
        metadata: Dict[str, Any] = None
    ):
        super().__init__(
            event_type="message.received",
            data={
                "message": message,
                "text": text or message.text,
                "message_type": message_type,
                "from_user": message.from_user.model_dump() if message.from_user else None,
                "chat": message.chat.model_dump() if message.chat else None
            },
            user_id=user_id,
            chat_id=chat_id,
            priority=EventPriority.NORMAL,
            metadata=metadata or {}
        )


@dataclass
class CallbackQueryEvent(Event):
    """Событие callback query (нажатие кнопки)"""

    def __init__(
        self,
        callback: CallbackQuery,
        user_id: int,
        callback_data: str,
        metadata: Dict[str, Any] = None
    ):
        super().__init__(
            event_type="callback.query",
            data={
                "callback": callback,
                "callback_data": callback_data,
                "message_id": callback.message.message_id if callback.message else None
            },
            user_id=user_id,
            chat_id=callback.message.chat.id if callback.message else None,
            priority=EventPriority.NORMAL,
            metadata=metadata or {}
        )


@dataclass
class ChatMemberEvent(Event):
    """Событие изменения участника чата (вход/выход/изменение прав)"""

    def __init__(
        self,
        update: ChatMemberUpdated,
        user_id: int,
        chat_id: int,
        action: str,  # joined, left, promoted, restricted
        metadata: Dict[str, Any] = None
    ):
        super().__init__(
            event_type="chat.member.updated",
            data={
                "update": update,
                "action": action,
                "old_status": update.old_chat_member.status,
                "new_status": update.new_chat_member.status
            },
            user_id=user_id,
            chat_id=chat_id,
            priority=EventPriority.NORMAL,
            metadata=metadata or {}
        )


# ========== БИЗНЕС-ЛОГИКА СОБЫТИЯ ==========

@dataclass
class TaskCreatedEvent(Event):
    """Событие создания задачи"""

    def __init__(
        self,
        task_id: str,
        task_title: str,
        created_by: int,
        assignee: Optional[str] = None,
        project: Optional[str] = None,
        metadata: Dict[str, Any] = None
    ):
        super().__init__(
            event_type="task.created",
            data={
                "task_id": task_id,
                "task_title": task_title,
                "created_by": created_by,
                "assignee": assignee,
                "project": project
            },
            user_id=created_by,
            priority=EventPriority.HIGH,
            metadata=metadata or {}
        )


@dataclass
class WorkJournalEntryEvent(Event):
    """Событие создания записи в журнале работ"""

    def __init__(
        self,
        entry_id: int,
        user_id: int,
        company: str,
        duration: str,
        description: str,
        metadata: Dict[str, Any] = None
    ):
        super().__init__(
            event_type="work_journal.entry.created",
            data={
                "entry_id": entry_id,
                "company": company,
                "duration": duration,
                "description": description
            },
            user_id=user_id,
            priority=EventPriority.NORMAL,
            metadata=metadata or {}
        )


# ========== AI СОБЫТИЯ ==========

@dataclass
class AIRequestEvent(Event):
    """Событие запроса к AI"""

    def __init__(
        self,
        prompt: str,
        user_id: int,
        chat_id: int,
        context: Optional[List[Dict[str, str]]] = None,
        model: str = "gpt-4",
        metadata: Dict[str, Any] = None
    ):
        super().__init__(
            event_type="ai.request",
            data={
                "prompt": prompt,
                "context": context or [],
                "model": model
            },
            user_id=user_id,
            chat_id=chat_id,
            priority=EventPriority.HIGH,
            metadata=metadata or {}
        )


@dataclass
class AIResponseEvent(Event):
    """Событие ответа от AI"""

    def __init__(
        self,
        response: str,
        user_id: int,
        chat_id: int,
        model: str,
        tokens_used: Optional[int] = None,
        processing_time: Optional[float] = None,
        metadata: Dict[str, Any] = None
    ):
        super().__init__(
            event_type="ai.response",
            data={
                "response": response,
                "model": model,
                "tokens_used": tokens_used,
                "processing_time": processing_time
            },
            user_id=user_id,
            chat_id=chat_id,
            priority=EventPriority.HIGH,
            metadata=metadata or {}
        )


@dataclass
class ChatSummaryRequestEvent(Event):
    """Событие запроса суммаризации чата"""

    def __init__(
        self,
        chat_id: int,
        messages: List[Message],
        requested_by: int,
        time_range: Optional[str] = None,
        metadata: Dict[str, Any] = None
    ):
        super().__init__(
            event_type="chat.summary.request",
            data={
                "messages": messages,
                "messages_count": len(messages),
                "time_range": time_range
            },
            user_id=requested_by,
            chat_id=chat_id,
            priority=EventPriority.HIGH,
            metadata=metadata or {}
        )


@dataclass
class AutoTaskDetectedEvent(Event):
    """Событие автоматического определения задачи из чата"""

    def __init__(
        self,
        chat_id: int,
        detected_task: str,
        confidence: float,
        source_message: Message,
        suggested_assignee: Optional[str] = None,
        metadata: Dict[str, Any] = None
    ):
        super().__init__(
            event_type="ai.auto_task.detected",
            data={
                "detected_task": detected_task,
                "confidence": confidence,
                "source_message": source_message,
                "suggested_assignee": suggested_assignee
            },
            user_id=source_message.from_user.id if source_message.from_user else None,
            chat_id=chat_id,
            priority=EventPriority.HIGH,
            metadata=metadata or {}
        )


# ========== СИСТЕМА СОБЫТИЯ ==========

@dataclass
class UserAuthenticatedEvent(Event):
    """Событие успешной авторизации пользователя"""

    def __init__(
        self,
        user_id: int,
        username: Optional[str] = None,
        role: str = "user",
        metadata: Dict[str, Any] = None
    ):
        super().__init__(
            event_type="user.authenticated",
            data={
                "username": username,
                "role": role
            },
            user_id=user_id,
            priority=EventPriority.NORMAL,
            metadata=metadata or {}
        )


@dataclass
class ErrorEvent(Event):
    """Событие ошибки"""

    def __init__(
        self,
        error: Exception,
        context: str,
        user_id: Optional[int] = None,
        chat_id: Optional[int] = None,
        metadata: Dict[str, Any] = None
    ):
        super().__init__(
            event_type="system.error",
            data={
                "error_type": type(error).__name__,
                "error_message": str(error),
                "context": context
            },
            user_id=user_id,
            chat_id=chat_id,
            priority=EventPriority.CRITICAL,
            metadata=metadata or {}
        )
