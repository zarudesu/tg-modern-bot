"""
Chat Context Service

Persistent storage and retrieval of chat messages for AI context.
Replaces in-memory MessageContextBuilder with database-backed storage.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import select, delete, func, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.database import get_async_session, AsyncSessionLocal
from ..database.chat_ai_models import ChatMessage, ChatAISettings, DetectedIssue, ThreadClientMapping
from ..utils.logger import bot_logger


class ChatContextService:
    """
    Service for managing persistent chat context.

    Features:
    - Store messages to database
    - Retrieve context for AI analysis
    - Manage per-chat settings
    - Track detected issues
    """

    # Default settings
    DEFAULT_CONTEXT_SIZE = 100
    DEFAULT_PROBLEM_KEYWORDS = [
        "не работает", "сломалось", "ошибка", "проблема", "баг",
        "не могу", "не получается", "помогите", "срочно", "критично",
        "упало", "висит", "тормозит", "глючит", "не отвечает"
    ]

    async def store_message(
        self,
        chat_id: int,
        message_id: int,
        user_id: int,
        username: Optional[str],
        display_name: Optional[str],
        message_text: Optional[str],
        message_type: str = 'text',
        reply_to_message_id: Optional[int] = None,
        thread_id: Optional[int] = None
    ) -> ChatMessage:
        """
        Store a message in the database.

        Args:
            chat_id: Telegram chat ID
            message_id: Telegram message ID
            user_id: User's Telegram ID
            username: User's @username
            display_name: User's display name
            message_text: Message content
            message_type: Type of message (text, voice, photo, etc.)
            reply_to_message_id: ID of message being replied to
            thread_id: Topic/thread ID for supergroups with topics

        Returns:
            Created ChatMessage object
        """
        async with AsyncSessionLocal() as session:
            message = ChatMessage(
                chat_id=chat_id,
                thread_id=thread_id,
                message_id=message_id,
                user_id=user_id,
                username=username,
                display_name=display_name,
                message_text=message_text,
                message_type=message_type,
                reply_to_message_id=reply_to_message_id
            )

            session.add(message)
            await session.commit()
            await session.refresh(message)

            bot_logger.debug(f"Stored message {message_id} from chat {chat_id}" +
                           (f" thread {thread_id}" if thread_id else ""))
            return message

    async def get_context(
        self,
        chat_id: int,
        limit: Optional[int] = None,
        since: Optional[datetime] = None,
        include_metadata: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get recent messages for AI context.

        Args:
            chat_id: Telegram chat ID
            limit: Max messages to return (uses chat settings if None)
            since: Only messages after this time
            include_metadata: Include AI analysis fields

        Returns:
            List of message dicts, newest first
        """
        async with AsyncSessionLocal() as session:
            # Get chat settings for context size
            if limit is None:
                settings = await self.get_chat_settings(chat_id, session)
                limit = settings.context_size if settings else self.DEFAULT_CONTEXT_SIZE

            # Build query
            query = select(ChatMessage).where(
                ChatMessage.chat_id == chat_id
            ).order_by(desc(ChatMessage.created_at)).limit(limit)

            if since:
                query = query.where(ChatMessage.created_at >= since)

            result = await session.execute(query)
            messages = result.scalars().all()

            # Format for AI context
            context = []
            for msg in reversed(messages):  # Oldest first for context
                entry = {
                    'user': msg.display_name or msg.username or str(msg.user_id),
                    'text': msg.message_text,
                    'time': msg.created_at.strftime('%H:%M') if msg.created_at else '',
                    'type': msg.message_type,
                }

                if include_metadata:
                    entry.update({
                        'message_id': msg.message_id,
                        'sentiment': msg.sentiment_score,
                        'is_question': msg.is_question,
                        'intent': msg.detected_intent,
                    })

                context.append(entry)

            return context

    async def get_context_as_text(
        self,
        chat_id: int,
        limit: Optional[int] = None,
        since: Optional[datetime] = None
    ) -> str:
        """
        Get context formatted as text for AI prompt.

        Returns:
            Formatted string like:
            [10:30] Костя: Привет, есть проблема с сервером
            [10:31] Дима: Какая именно?
            ...
        """
        context = await self.get_context(chat_id, limit, since)

        lines = []
        for msg in context:
            time_str = f"[{msg['time']}]" if msg['time'] else ""
            user = msg['user']
            text = msg['text'] or f"[{msg['type']}]"
            lines.append(f"{time_str} {user}: {text}")

        return "\n".join(lines)

    async def get_chat_settings(
        self,
        chat_id: int,
        session: Optional[AsyncSession] = None
    ) -> Optional[ChatAISettings]:
        """Get AI settings for a chat"""
        should_close = session is None
        if session is None:
            session = AsyncSessionLocal()

        try:
            result = await session.execute(
                select(ChatAISettings).where(ChatAISettings.chat_id == chat_id)
            )
            return result.scalar_one_or_none()
        finally:
            if should_close:
                await session.close()

    async def get_or_create_settings(
        self,
        chat_id: int,
        chat_title: Optional[str] = None
    ) -> ChatAISettings:
        """Get or create AI settings for a chat"""
        async with AsyncSessionLocal() as session:
            settings = await self.get_chat_settings(chat_id, session)

            if not settings:
                settings = ChatAISettings(
                    chat_id=chat_id,
                    chat_title=chat_title,
                    context_size=self.DEFAULT_CONTEXT_SIZE
                )
                session.add(settings)
                await session.commit()
                await session.refresh(settings)
                bot_logger.info(f"Created AI settings for chat {chat_id}")

            return settings

    async def update_settings(
        self,
        chat_id: int,
        **kwargs
    ) -> ChatAISettings:
        """Update AI settings for a chat"""
        async with AsyncSessionLocal() as session:
            settings = await self.get_chat_settings(chat_id, session)

            if not settings:
                settings = ChatAISettings(chat_id=chat_id)
                session.add(settings)

            for key, value in kwargs.items():
                if hasattr(settings, key):
                    setattr(settings, key, value)

            await session.commit()
            await session.refresh(settings)
            return settings

    async def store_detected_issue(
        self,
        chat_id: int,
        issue_type: str,
        message_id: Optional[int] = None,
        user_id: Optional[int] = None,
        confidence: Optional[float] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        original_text: Optional[str] = None,
        ai_response_json: Optional[str] = None,
        ai_model_used: Optional[str] = None
    ) -> DetectedIssue:
        """Store a detected issue"""
        async with AsyncSessionLocal() as session:
            issue = DetectedIssue(
                chat_id=chat_id,
                message_id=message_id,
                user_id=user_id,
                issue_type=issue_type,
                confidence=confidence,
                title=title,
                description=description,
                original_text=original_text,
                status='new',
                ai_response_json=ai_response_json,
                ai_model_used=ai_model_used
            )

            session.add(issue)
            await session.commit()
            await session.refresh(issue)

            bot_logger.info(f"Stored detected issue: {issue_type} in chat {chat_id}")
            return issue

    async def get_pending_issues(
        self,
        chat_id: int,
        issue_type: Optional[str] = None
    ) -> List[DetectedIssue]:
        """Get unresolved issues for a chat"""
        async with AsyncSessionLocal() as session:
            query = select(DetectedIssue).where(
                and_(
                    DetectedIssue.chat_id == chat_id,
                    DetectedIssue.status.in_(['new', 'notified'])
                )
            ).order_by(desc(DetectedIssue.created_at))

            if issue_type:
                query = query.where(DetectedIssue.issue_type == issue_type)

            result = await session.execute(query)
            return list(result.scalars().all())

    async def update_issue_status(
        self,
        issue_id: int,
        status: str,
        resolved_by: Optional[int] = None,
        plane_issue_id: Optional[str] = None
    ) -> Optional[DetectedIssue]:
        """Update issue status"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(DetectedIssue).where(DetectedIssue.id == issue_id)
            )
            issue = result.scalar_one_or_none()

            if issue:
                issue.status = status
                if status == 'resolved':
                    issue.resolved_at = datetime.utcnow()
                    issue.resolved_by = resolved_by
                if status == 'notified':
                    issue.notified_at = datetime.utcnow()
                if plane_issue_id:
                    issue.plane_issue_id = plane_issue_id

                await session.commit()
                await session.refresh(issue)

            return issue

    async def cleanup_old_messages(
        self,
        days: int = 365,
        chat_id: Optional[int] = None
    ) -> int:
        """
        Remove messages older than specified days.

        Args:
            days: Delete messages older than this
            chat_id: Optional - only clean specific chat

        Returns:
            Number of deleted messages
        """
        async with AsyncSessionLocal() as session:
            cutoff = datetime.utcnow() - timedelta(days=days)

            query = delete(ChatMessage).where(
                ChatMessage.created_at < cutoff
            )

            if chat_id:
                query = query.where(ChatMessage.chat_id == chat_id)

            result = await session.execute(query)
            await session.commit()

            deleted = result.rowcount
            if deleted > 0:
                bot_logger.info(f"Cleaned up {deleted} old messages (older than {days} days)")

            return deleted

    async def get_message_count(self, chat_id: int) -> int:
        """Get total message count for a chat"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(func.count(ChatMessage.id)).where(
                    ChatMessage.chat_id == chat_id
                )
            )
            return result.scalar() or 0

    async def get_unanswered_questions(
        self,
        chat_id: int,
        minutes: int = 30
    ) -> List[ChatMessage]:
        """
        Find questions without replies within specified time.

        Args:
            chat_id: Chat to check
            minutes: Questions older than this without reply

        Returns:
            List of unanswered question messages
        """
        async with AsyncSessionLocal() as session:
            cutoff = datetime.utcnow() - timedelta(minutes=minutes)

            # Get questions that:
            # 1. Were asked before cutoff
            # 2. Are marked as questions
            # 3. Are not answered
            result = await session.execute(
                select(ChatMessage).where(
                    and_(
                        ChatMessage.chat_id == chat_id,
                        ChatMessage.is_question == True,
                        ChatMessage.is_answered == False,
                        ChatMessage.created_at < cutoff
                    )
                ).order_by(ChatMessage.created_at)
            )

            return list(result.scalars().all())

    # ==================== Thread Client Mapping ====================

    async def create_thread_mapping(
        self,
        work_group_id: int,
        thread_id: int,
        client_chat_id: int,
        client_name: str,
        thread_name: Optional[str] = None,
        plane_project_id: Optional[str] = None,
        created_by: Optional[int] = None
    ) -> ThreadClientMapping:
        """
        Create a mapping between admin work group thread and client chat.

        Args:
            work_group_id: Admin work group chat_id
            thread_id: Thread ID in work group
            client_chat_id: Client's group chat_id
            client_name: Client name (e.g., "DELTA")
            thread_name: Thread name for display
            plane_project_id: Optional Plane project ID
            created_by: Admin who created mapping

        Returns:
            Created ThreadClientMapping
        """
        async with AsyncSessionLocal() as session:
            mapping = ThreadClientMapping(
                work_group_id=work_group_id,
                thread_id=thread_id,
                client_chat_id=client_chat_id,
                client_name=client_name,
                thread_name=thread_name,
                plane_project_id=plane_project_id,
                created_by=created_by,
                is_active=True
            )

            session.add(mapping)
            await session.commit()
            await session.refresh(mapping)

            bot_logger.info(f"Created thread mapping: thread {thread_id} -> client {client_name} (chat {client_chat_id})")
            return mapping

    async def get_mapping_by_thread(
        self,
        thread_id: int,
        work_group_id: Optional[int] = None
    ) -> Optional[ThreadClientMapping]:
        """Get mapping for a specific thread"""
        async with AsyncSessionLocal() as session:
            query = select(ThreadClientMapping).where(
                and_(
                    ThreadClientMapping.thread_id == thread_id,
                    ThreadClientMapping.is_active == True
                )
            )

            if work_group_id:
                query = query.where(ThreadClientMapping.work_group_id == work_group_id)

            result = await session.execute(query)
            return result.scalar_one_or_none()

    async def get_mapping_by_client(
        self,
        client_name: str
    ) -> Optional[ThreadClientMapping]:
        """Get mapping for a client by name"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ThreadClientMapping).where(
                    and_(
                        ThreadClientMapping.client_name == client_name,
                        ThreadClientMapping.is_active == True
                    )
                )
            )
            return result.scalar_one_or_none()

    async def get_all_mappings(
        self,
        work_group_id: Optional[int] = None
    ) -> List[ThreadClientMapping]:
        """Get all active thread mappings"""
        async with AsyncSessionLocal() as session:
            query = select(ThreadClientMapping).where(
                ThreadClientMapping.is_active == True
            ).order_by(ThreadClientMapping.client_name)

            if work_group_id:
                query = query.where(ThreadClientMapping.work_group_id == work_group_id)

            result = await session.execute(query)
            return list(result.scalars().all())

    async def delete_mapping(
        self,
        mapping_id: int
    ) -> bool:
        """Soft delete a mapping (set is_active=False)"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ThreadClientMapping).where(ThreadClientMapping.id == mapping_id)
            )
            mapping = result.scalar_one_or_none()

            if mapping:
                mapping.is_active = False
                await session.commit()
                bot_logger.info(f"Deleted thread mapping {mapping_id}: {mapping.client_name}")
                return True

            return False

    async def get_context_for_thread(
        self,
        thread_id: int,
        work_group_id: Optional[int] = None,
        limit: Optional[int] = None
    ) -> tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Get context from CLIENT CHAT for a work group thread.

        Args:
            thread_id: Thread ID in work group
            work_group_id: Work group chat_id
            limit: Max messages

        Returns:
            Tuple of (context list, client_name) or ([], None) if no mapping
        """
        mapping = await self.get_mapping_by_thread(thread_id, work_group_id)

        if not mapping:
            return [], None

        context = await self.get_context(
            chat_id=mapping.client_chat_id,
            limit=limit
        )

        return context, mapping.client_name

    async def get_context_as_text_for_thread(
        self,
        thread_id: int,
        work_group_id: Optional[int] = None,
        limit: Optional[int] = None
    ) -> tuple[str, Optional[str]]:
        """
        Get context as text from CLIENT CHAT for a work group thread.

        Returns:
            Tuple of (context text, client_name) or ("", None) if no mapping
        """
        mapping = await self.get_mapping_by_thread(thread_id, work_group_id)

        if not mapping:
            return "", None

        context_text = await self.get_context_as_text(
            chat_id=mapping.client_chat_id,
            limit=limit
        )

        return context_text, mapping.client_name


# Global instance
chat_context_service = ChatContextService()
