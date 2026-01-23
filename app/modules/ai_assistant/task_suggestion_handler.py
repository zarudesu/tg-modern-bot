"""
Smart Task Detection - обработчик предложений по созданию задач

Слушает события AutoTaskDetectedEvent и отправляет в группу
предложение создать задачу с кнопкой быстрого создания.
"""
from typing import List

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from ...core.events.event_bus import EventHandler, Event, EventPriority, event_bus
from ...core.events.events import AutoTaskDetectedEvent
from ...utils.logger import bot_logger
from ...config import settings


# Cache for recent suggestions to avoid spam
_recent_suggestions: dict = {}  # chat_id -> last_suggestion_time


class TaskSuggestionHandler(EventHandler):
    """
    Обработчик предложений по созданию задач

    Когда AI обнаруживает задачу в сообщении, этот обработчик
    отправляет в чат предложение создать задачу в Plane.
    """

    # Минимальный интервал между предложениями (секунды)
    MIN_SUGGESTION_INTERVAL = 30

    # Минимальная уверенность для показа предложения
    MIN_CONFIDENCE = 0.75

    @property
    def event_types(self) -> List[str]:
        return ["ai.auto_task.detected"]

    @property
    def priority(self) -> EventPriority:
        return EventPriority.NORMAL

    def __init__(self, bot: Bot):
        self.bot = bot

    async def handle(self, event: Event):
        if not isinstance(event, AutoTaskDetectedEvent):
            return

        chat_id = event.chat_id
        confidence = event.data.get("confidence", 0)
        detected_task = event.data.get("detected_task", "")
        source_message = event.data.get("source_message")
        suggested_assignee = event.data.get("suggested_assignee")

        # Проверяем уверенность
        if confidence < self.MIN_CONFIDENCE:
            bot_logger.debug(
                f"Task suggestion skipped: low confidence ({confidence:.2f})"
            )
            return

        # Проверяем интервал между предложениями
        import time
        now = time.time()
        last_suggestion = _recent_suggestions.get(chat_id, 0)

        if now - last_suggestion < self.MIN_SUGGESTION_INTERVAL:
            bot_logger.debug(
                f"Task suggestion skipped: too soon after last suggestion"
            )
            return

        # Запоминаем время предложения
        _recent_suggestions[chat_id] = now

        try:
            # Формируем сообщение с предложением
            user_mention = ""
            if source_message and source_message.from_user:
                if source_message.from_user.username:
                    user_mention = f"@{source_message.from_user.username}"
                else:
                    user_mention = source_message.from_user.first_name

            # Экранируем HTML
            task_escaped = detected_task.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

            suggestion_text = (
                f"🤖 <b>Обнаружена задача!</b>\n\n"
                f"<i>{task_escaped}</i>\n\n"
            )

            if suggested_assignee:
                assignee_escaped = suggested_assignee.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                suggestion_text += f"👤 Возможный исполнитель: {assignee_escaped}\n"

            suggestion_text += f"📊 Уверенность: {confidence:.0%}\n\n"
            suggestion_text += f"<i>Нажмите кнопку для создания задачи в Plane</i>"

            # Создаём клавиатуру с кнопкой создания задачи
            # Сохраняем данные в callback_data (ограничение 64 байта)
            # Используем ID исходного сообщения для восстановления контекста
            message_id = source_message.message_id if source_message else 0

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Создать задачу",
                        callback_data=f"smart_task:create:{chat_id}:{message_id}"
                    ),
                    InlineKeyboardButton(
                        text="❌ Игнорировать",
                        callback_data=f"smart_task:ignore:{chat_id}:{message_id}"
                    )
                ]
            ])

            # Отправляем предложение в чат (как reply к исходному сообщению)
            await self.bot.send_message(
                chat_id=chat_id,
                text=suggestion_text,
                parse_mode="HTML",
                reply_markup=keyboard,
                reply_to_message_id=message_id if message_id else None
            )

            bot_logger.info(
                f"Task suggestion sent to chat {chat_id}: {detected_task[:50]}..."
            )

        except Exception as e:
            bot_logger.error(f"Failed to send task suggestion: {e}")


# Store detected tasks for callback handling
_detected_tasks: dict = {}  # "chat_id:message_id" -> task_data


def store_detected_task(chat_id: int, message_id: int, task_data: dict):
    """Store detected task data for later retrieval"""
    key = f"{chat_id}:{message_id}"
    _detected_tasks[key] = task_data

    # Clean old entries (keep last 100)
    if len(_detected_tasks) > 100:
        oldest_keys = sorted(_detected_tasks.keys())[:50]
        for k in oldest_keys:
            del _detected_tasks[k]


def get_detected_task(chat_id: int, message_id: int) -> dict:
    """Retrieve stored task data"""
    key = f"{chat_id}:{message_id}"
    return _detected_tasks.get(key)


# Global handler instance (initialized in main.py)
task_suggestion_handler: TaskSuggestionHandler = None


async def init_task_suggestion_handler(bot: Bot):
    """Initialize and register the task suggestion handler"""
    global task_suggestion_handler
    task_suggestion_handler = TaskSuggestionHandler(bot)
    event_bus.register_handler(task_suggestion_handler)
    bot_logger.info("Task suggestion handler registered")
