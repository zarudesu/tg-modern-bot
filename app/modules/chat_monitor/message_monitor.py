"""
Мониторинг сообщений в чатах

Читает все сообщения и:
1. Сохраняет в БД для контекста (ChatContextService)
2. Публикует события для Event Bus
3. Детектирует проблемы (ProblemDetector)
4. Отправляет на AI анализ через n8n (детекция задач)
"""
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import BaseFilter
from typing import List, Optional

from ...core.events.event_bus import event_bus, EventHandler, Event
from ...core.events.events import MessageReceivedEvent
from ...services.n8n_ai_service import n8n_ai_service
from ...services.chat_context_service import chat_context_service
from ...services.problem_detector_service import problem_detector
from ...utils.logger import bot_logger
from ...config import settings

router = Router()


class NotInSupportRequestFilter(BaseFilter):
    """Filter to exclude messages when user has active support request (FSM state)"""

    async def __call__(self, message: Message) -> bool:
        # Import here to avoid circular dependency
        from ..chat_support.states import SupportRequestStates
        from aiogram.fsm.context import FSMContext
        from aiogram.fsm.storage.base import StorageKey

        # Access FSM storage through message bot
        try:
            # Get current state for this user in this chat
            state_key = StorageKey(
                bot_id=message.bot.id,
                chat_id=message.chat.id,
                user_id=message.from_user.id
            )

            # Get FSM storage from bot
            storage = message.bot.fsm.storage if hasattr(message.bot, 'fsm') else None
            if not storage:
                # No FSM storage available, allow message
                return True

            # Get current state
            state_data = await storage.get_state(state_key)

            # Check if user is in support request state
            is_in_support_state = (
                state_data is not None and
                state_data.startswith('SupportRequestStates:')
            )

            if is_in_support_state:
                bot_logger.info(f"🚫 Chat Monitor: Skipping message (user in FSM state: {state_data})")

            # Return True if NOT in support state (allow Chat Monitor)
            return not is_in_support_state

        except Exception as e:
            bot_logger.error(f"Error checking FSM state in filter: {e}")
            # On error, allow message to be processed
            return True


async def _detect_and_notify_problem(message: Message):
    """
    Detect problems in message and send alert to group.

    Uses ProblemDetector for keyword + AI analysis.
    Alerts go to the same group chat.
    """
    try:
        # Check if problem detection is enabled
        chat_settings = await chat_context_service.get_chat_settings(message.chat.id)
        if chat_settings and not chat_settings.problem_detection_enabled:
            return

        # Analyze message
        detection_result = await problem_detector.analyze_message(
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            username=message.from_user.full_name or message.from_user.username,
            message_text=message.text,
            use_ai=True  # Use AI for semantic analysis
        )

        if not detection_result:
            return

        # Store detected issue in DB
        await chat_context_service.store_detected_issue(
            chat_id=message.chat.id,
            issue_type=detection_result.problem_type,
            message_id=message.message_id,
            user_id=message.from_user.id,
            confidence=detection_result.confidence,
            title=detection_result.title,
            description=detection_result.description,
            original_text=message.text
        )

        # Send alert to group (reply to original message)
        alert_text = _format_problem_alert(detection_result, message.from_user.full_name)
        await message.reply(
            alert_text,
            parse_mode="HTML",
            disable_notification=True  # Silent notification
        )

        bot_logger.info(
            f"Problem detected in chat {message.chat.id}: {detection_result.problem_type}",
            extra={
                "confidence": detection_result.confidence,
                "keywords": detection_result.keywords_matched
            }
        )

    except Exception as e:
        bot_logger.error(f"Problem detection failed: {e}")


def _format_problem_alert(result, username: str) -> str:
    """Format problem detection result as Telegram message"""
    # Emoji based on type
    type_emoji = {
        "urgent": "🚨",
        "problem": "⚠️",
        "question": "❓",
        "complaint": "😤"
    }
    emoji = type_emoji.get(result.problem_type, "📋")

    # Confidence indicator
    if result.confidence >= 0.8:
        conf_str = "высокая"
    elif result.confidence >= 0.6:
        conf_str = "средняя"
    else:
        conf_str = "низкая"

    lines = [
        f"{emoji} <b>Обнаружена проблема</b>",
        f"",
        f"<b>Тип:</b> {result.problem_type}",
        f"<b>Уверенность:</b> {conf_str} ({result.confidence:.0%})",
        f"",
        f"<b>Краткое описание:</b>",
        f"{result.title}",
    ]

    if result.keywords_matched:
        keywords_str = ", ".join(result.keywords_matched[:5])
        lines.append(f"")
        lines.append(f"<i>Ключевые слова: {keywords_str}</i>")

    # Suggested action
    action_text = {
        "create_task": "💼 Рекомендуется создать задачу",
        "notify": "👀 Требует внимания",
        "auto_reply": "💬 Можно ответить автоматически"
    }
    if result.suggested_action in action_text:
        lines.append(f"")
        lines.append(action_text[result.suggested_action])

    return "\n".join(lines)


async def get_chat_plane_mapping(chat_id: int) -> Optional[dict]:
    """
    Получить маппинг чата на проект Plane.

    Returns:
        dict с plane_project_id и plane_project_name или None
    """
    try:
        from ...database.database import get_async_session
        from ...database.chat_support_models import ChatPlaneMapping
        from sqlalchemy import select

        async for session in get_async_session():
            result = await session.execute(
                select(ChatPlaneMapping).where(
                    ChatPlaneMapping.chat_id == chat_id,
                    ChatPlaneMapping.is_active == True
                )
            )
            mapping = result.scalar_one_or_none()

            if mapping:
                return {
                    "plane_project_id": mapping.plane_project_id,
                    "plane_project_name": mapping.plane_project_name
                }
            return None
    except Exception as e:
        bot_logger.error(f"Error getting chat-plane mapping: {e}")
        return None


@router.message(
    F.chat.type.in_(["group", "supergroup"]),
    ~(F.text & F.text.startswith("/")),  # Игнорируем команды
    NotInSupportRequestFilter()  # Игнорируем активные support requests
)
async def monitor_group_message(message: Message):
    """
    Мониторинг сообщений в группах

    1. Сохраняет в БД (persistent context)
    2. Публикует событие в Event Bus
    3. Детектирует проблемы (AI)
    4. Отправляет на AI анализ в n8n (для детекции задач)
    """
    try:
        # ==================== 0. DETERMINE MESSAGE TYPE ====================
        message_type = "text"
        if message.photo:
            message_type = "photo"
        elif message.document:
            message_type = "document"
        elif message.voice:
            message_type = "voice"
        elif message.video:
            message_type = "video"

        # ==================== 1. PERSISTENT CONTEXT ====================
        # Сохраняем сообщение в БД для долгосрочного контекста
        try:
            await chat_context_service.store_message(
                chat_id=message.chat.id,
                message_id=message.message_id,
                user_id=message.from_user.id,
                username=message.from_user.username,
                display_name=message.from_user.full_name,
                message_text=message.text or message.caption,
                message_type=message_type,
                reply_to_message_id=message.reply_to_message.message_id if message.reply_to_message else None
            )
        except Exception as e:
            bot_logger.warning(f"Failed to store message in DB: {e}")

        # ==================== 2. EVENT BUS ====================
        # Создаём событие
        event = MessageReceivedEvent(
            message=message,
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            text=message.text or message.caption,
            message_type=message_type,
            metadata={
                "chat_title": message.chat.title,
                "chat_type": message.chat.type,
                "from_user_name": message.from_user.full_name
            }
        )

        # Публикуем событие (асинхронно, без ожидания)
        await event_bus.publish(event, wait=False)

        bot_logger.debug(
            f"Group message monitored: {message.text[:50] if message.text else message_type}",
            extra={
                "chat_id": message.chat.id,
                "user_id": message.from_user.id
            }
        )

        # ==================== 3. PROBLEM DETECTION ====================
        # Детектируем проблемы в текстовых сообщениях
        if message_type == "text" and message.text:
            await _detect_and_notify_problem(message)

        # ==================== 2. AI TASK DETECTION ====================
        # Проверяем, включена ли AI детекция
        if not getattr(settings, 'ai_task_detection_enabled', True):
            return

        # Проверяем, настроен ли n8n
        if not getattr(settings, 'n8n_url', None):
            return

        # Только текстовые сообщения для AI анализа
        if message_type != "text" or not message.text:
            return

        # Получаем маппинг чата на Plane проект
        mapping = await get_chat_plane_mapping(message.chat.id)

        # Если чат не замаплен на проект - пропускаем AI анализ
        # (задачи создаются только для замапленных чатов)
        if not mapping:
            bot_logger.debug(
                f"Chat {message.chat.id} not mapped to Plane project, skipping AI analysis"
            )
            return

        # Отправляем на AI анализ
        success, result = await n8n_ai_service.analyze_message_for_task(
            message=message,
            plane_project_id=mapping.get("plane_project_id"),
            plane_project_name=mapping.get("plane_project_name")
        )

        if success:
            bot_logger.info(
                f"Message sent to AI for task detection",
                extra={
                    "chat_id": message.chat.id,
                    "chat_title": message.chat.title,
                    "plane_project": mapping.get("plane_project_name")
                }
            )
        elif result and result.get("skipped"):
            # Нормальный skip (rate limit, too short, etc.)
            bot_logger.debug(f"AI analysis skipped: {result.get('skipped')}")
        else:
            bot_logger.warning(
                f"Failed to send message to AI",
                extra={"error": result}
            )

    except Exception as e:
        bot_logger.error(f"Message monitoring error: {e}")


class MessageContextBuilder(EventHandler):
    """
    Обработчик для построения контекста из сообщений.

    DEPRECATED: In-memory storage is kept for backwards compatibility.
    New code should use chat_context_service for persistent context.

    Use get_context_from_db() for DB-backed context.
    """

    def __init__(self, max_messages: int = 50):
        self.max_messages = max_messages
        self.chat_contexts: dict = {}  # chat_id -> List[Message] (in-memory cache)

    @property
    def event_types(self) -> List[str]:
        return ["message.received"]

    async def handle(self, event: Event):
        if not isinstance(event, MessageReceivedEvent):
            return

        chat_id = event.chat_id
        message = event.data.get("message")

        if not message:
            return

        # In-memory cache (for backwards compatibility)
        if chat_id not in self.chat_contexts:
            self.chat_contexts[chat_id] = []

        self.chat_contexts[chat_id].append(message)

        if len(self.chat_contexts[chat_id]) > self.max_messages:
            self.chat_contexts[chat_id] = self.chat_contexts[chat_id][-self.max_messages:]

        bot_logger.debug(
            f"Message added to context",
            extra={
                "chat_id": chat_id,
                "context_size": len(self.chat_contexts[chat_id])
            }
        )

    def get_context(self, chat_id: int, limit: int = 10) -> List[Message]:
        """
        Получить контекст чата из памяти (последние N сообщений).

        DEPRECATED: Use get_context_from_db() for persistent context.
        """
        context = self.chat_contexts.get(chat_id, [])
        return context[-limit:] if limit else context

    async def get_context_from_db(self, chat_id: int, limit: int = 100) -> List[dict]:
        """
        Получить контекст чата из БД (persistent).

        Returns list of message dicts with keys:
        - user, text, time, type, message_id, sentiment, is_question, intent
        """
        return await chat_context_service.get_context(
            chat_id=chat_id,
            limit=limit,
            include_metadata=True
        )

    async def get_context_as_text(self, chat_id: int, limit: int = 100) -> str:
        """
        Получить контекст как текст для AI промпта.

        Returns formatted text:
        [10:30] User: Message text
        [10:31] Another: Reply
        """
        return await chat_context_service.get_context_as_text(
            chat_id=chat_id,
            limit=limit
        )

    def clear_context(self, chat_id: int):
        """Очистить контекст чата (только in-memory)"""
        if chat_id in self.chat_contexts:
            del self.chat_contexts[chat_id]


# Глобальный экземпляр для доступа из других модулей
message_context_builder = MessageContextBuilder()

# Регистрируем обработчик
event_bus.register_handler(message_context_builder)
