"""
Summary Service

AI-powered chat summarization for group discussions.
Generates daily summaries, on-demand summaries, and key highlights.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from ..core.ai.ai_manager import ai_manager
from ..services.chat_context_service import chat_context_service
from ..utils.logger import bot_logger


@dataclass
class ChatSummary:
    """Result of chat summarization"""
    summary_text: str
    key_topics: List[str]
    active_users: List[str]
    open_questions: List[str]
    detected_issues: List[str]
    message_count: int
    time_range: str  # e.g., "последние 2 часа"
    generated_at: datetime


class SummaryService:
    """
    Service for generating AI-powered chat summaries.

    Features:
    - On-demand summaries (last N messages or time period)
    - Daily automatic summaries
    - Key topic extraction
    - Open questions tracking
    - Issue highlighting
    """

    # Summary configurations
    DEFAULT_MESSAGE_LIMIT = 100
    MIN_MESSAGES_FOR_SUMMARY = 10

    async def generate_summary(
        self,
        chat_id: int,
        limit: Optional[int] = None,
        since: Optional[datetime] = None,
        summary_type: str = "general"  # general, daily, brief
    ) -> Optional[ChatSummary]:
        """
        Generate a summary of recent chat messages.

        Args:
            chat_id: Telegram chat ID
            limit: Max messages to include
            since: Only messages after this time
            summary_type: Type of summary to generate

        Returns:
            ChatSummary if successful, None otherwise
        """
        try:
            # Get context
            if limit is None:
                limit = self.DEFAULT_MESSAGE_LIMIT

            context = await chat_context_service.get_context(
                chat_id=chat_id,
                limit=limit,
                since=since,
                include_metadata=True
            )

            if len(context) < self.MIN_MESSAGES_FOR_SUMMARY:
                bot_logger.info(
                    f"Not enough messages for summary in chat {chat_id}: "
                    f"{len(context)} < {self.MIN_MESSAGES_FOR_SUMMARY}"
                )
                return None

            # Format context for AI
            context_text = await chat_context_service.get_context_as_text(
                chat_id=chat_id,
                limit=limit,
                since=since
            )

            # Get time range description
            time_range = self._calculate_time_range(context)

            # Generate summary with AI
            ai_result = await self._generate_with_ai(
                context_text=context_text,
                summary_type=summary_type,
                message_count=len(context)
            )

            if not ai_result:
                return None

            # Extract active users from context
            active_users = self._extract_active_users(context)

            return ChatSummary(
                summary_text=ai_result.get('summary', 'Не удалось создать резюме'),
                key_topics=ai_result.get('topics', []),
                active_users=active_users,
                open_questions=ai_result.get('questions', []),
                detected_issues=ai_result.get('issues', []),
                message_count=len(context),
                time_range=time_range,
                generated_at=datetime.utcnow()
            )

        except Exception as e:
            bot_logger.error(f"Summary generation failed for chat {chat_id}: {e}")
            return None

    async def generate_daily_summary(
        self,
        chat_id: int,
        date: Optional[datetime] = None
    ) -> Optional[ChatSummary]:
        """
        Generate daily summary for a chat.

        Args:
            chat_id: Telegram chat ID
            date: Date to summarize (defaults to today)

        Returns:
            ChatSummary for the day
        """
        if date is None:
            date = datetime.utcnow()

        # Get start and end of day
        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        return await self.generate_summary(
            chat_id=chat_id,
            limit=500,  # More messages for daily
            since=start_of_day,
            summary_type="daily"
        )

    async def get_quick_brief(
        self,
        chat_id: int,
        last_n_messages: int = 50
    ) -> Optional[str]:
        """
        Get a quick one-paragraph brief of recent discussion.

        Args:
            chat_id: Telegram chat ID
            last_n_messages: How many recent messages to summarize

        Returns:
            Brief text or None
        """
        summary = await self.generate_summary(
            chat_id=chat_id,
            limit=last_n_messages,
            summary_type="brief"
        )

        if summary:
            return summary.summary_text
        return None

    async def _generate_with_ai(
        self,
        context_text: str,
        summary_type: str,
        message_count: int
    ) -> Optional[Dict[str, Any]]:
        """Generate summary using AI"""
        try:
            system_prompt = self._get_system_prompt(summary_type)
            user_prompt = f"""Проанализируй следующий чат ({message_count} сообщений):

{context_text}

Создай резюме согласно инструкциям."""

            response = await ai_manager.chat(
                user_message=user_prompt,
                system_prompt=system_prompt
            )

            if response and response.content:
                import json
                content = response.content.strip()

                # Clean up markdown if present
                if content.startswith("```"):
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]
                    content = content.strip()

                return json.loads(content)

        except Exception as e:
            bot_logger.warning(f"AI summary generation failed: {e}")

        return None

    def _get_system_prompt(self, summary_type: str) -> str:
        """Get appropriate system prompt based on summary type"""

        base_prompt = """Ты — ассистент для анализа рабочих чатов.
Твоя задача — создавать краткие и полезные резюме обсуждений.

Отвечай ТОЛЬКО JSON (без markdown):
{
    "summary": "краткое резюме обсуждения (2-5 предложений)",
    "topics": ["тема 1", "тема 2", ...],
    "questions": ["нерешённый вопрос 1", ...],
    "issues": ["проблема или жалоба 1", ...]
}

Правила:
- summary: что обсуждали, какие решения приняли
- topics: ключевые темы (до 5)
- questions: вопросы без ответа
- issues: упомянутые проблемы, жалобы, технические сложности
"""

        if summary_type == "daily":
            return base_prompt + """

Это дневное резюме. Включи:
- Общий обзор дня
- Ключевые решения
- Что осталось нерешённым
"""

        if summary_type == "brief":
            return base_prompt + """

Это краткий обзор. Сделай summary максимально кратким (1-2 предложения).
topics и issues можно оставить пустыми если не критичны.
"""

        return base_prompt

    def _calculate_time_range(self, context: List[Dict]) -> str:
        """Calculate human-readable time range"""
        if not context:
            return "нет сообщений"

        # Context is oldest first
        first_time = context[0].get('time', '')
        last_time = context[-1].get('time', '')

        if first_time and last_time:
            return f"{first_time} — {last_time}"

        return "последние сообщения"

    def _extract_active_users(self, context: List[Dict]) -> List[str]:
        """Extract list of active users from context"""
        users = {}
        for msg in context:
            user = msg.get('user', 'Unknown')
            users[user] = users.get(user, 0) + 1

        # Sort by message count, return top 10
        sorted_users = sorted(users.items(), key=lambda x: x[1], reverse=True)
        return [user for user, count in sorted_users[:10]]

    def format_summary_message(self, summary: ChatSummary) -> str:
        """Format summary for Telegram message"""
        lines = []

        # Header
        lines.append(f"📊 <b>Резюме чата</b>")
        lines.append(f"<i>{summary.time_range} • {summary.message_count} сообщений</i>")
        lines.append("")

        # Main summary
        lines.append(f"📝 {summary.summary_text}")
        lines.append("")

        # Topics
        if summary.key_topics:
            lines.append("<b>🏷 Темы:</b>")
            for topic in summary.key_topics[:5]:
                lines.append(f"  • {topic}")
            lines.append("")

        # Open questions
        if summary.open_questions:
            lines.append("<b>❓ Открытые вопросы:</b>")
            for q in summary.open_questions[:5]:
                lines.append(f"  • {q}")
            lines.append("")

        # Issues
        if summary.detected_issues:
            lines.append("<b>⚠️ Проблемы:</b>")
            for issue in summary.detected_issues[:5]:
                lines.append(f"  • {issue}")
            lines.append("")

        # Active users
        if summary.active_users:
            users_str = ", ".join(summary.active_users[:5])
            if len(summary.active_users) > 5:
                users_str += f" и ещё {len(summary.active_users) - 5}"
            lines.append(f"<b>👥 Участники:</b> {users_str}")

        return "\n".join(lines)


# Global instance
summary_service = SummaryService()
