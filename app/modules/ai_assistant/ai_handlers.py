"""
AI обработчики через Event Bus

Реагируют на события и обрабатывают их с помощью AI
"""
from aiogram import Router
from typing import List

from ...core.events.event_bus import EventHandler, Event, EventPriority, event_bus
from ...core.events.events import MessageReceivedEvent, AutoTaskDetectedEvent
from ...core.ai.ai_manager import ai_manager
from ...utils.logger import bot_logger

router = Router()


class AutoTaskDetectionHandler(EventHandler):
    """
    Обработчик автоматического определения задач из сообщений

    Анализирует сообщения с помощью AI и определяет, содержат ли они задачи
    """

    @property
    def event_types(self) -> List[str]:
        return ["message.received"]

    @property
    def priority(self) -> EventPriority:
        return EventPriority.HIGH

    async def handle(self, event: Event):
        if not isinstance(event, MessageReceivedEvent):
            return

        message = event.data.get("message")
        text = event.data.get("text")

        if not text or len(text) < 10:  # Игнорируем короткие сообщения
            return

        # Проверяем ключевые слова которые могут указывать на задачу
        task_keywords = ["нужно", "надо", "сделать", "создать", "добавить", "исправить", "fix", "todo"]

        if not any(keyword in text.lower() for keyword in task_keywords):
            return

        try:
            # Используем AI для определения задачи
            prompt = f"""
Проанализируй следующее сообщение и определи, содержит ли оно задачу или поручение.

Сообщение: "{text}"

Если это задача, ответь в формате JSON:
{{
    "is_task": true,
    "task_description": "краткое описание задачи",
    "confidence": 0.9,
    "suggested_assignee": "имя исполнителя если указано или null"
}}

Если это НЕ задача, ответь:
{{
    "is_task": false
}}
"""

            response = await ai_manager.chat(
                user_message=prompt,
                system_prompt="Ты - эксперт по анализу текста для определения задач."
            )

            # Парсим ответ
            import json
            try:
                result = json.loads(response.content)

                if result.get("is_task") and result.get("confidence", 0) > 0.7:
                    # Store detected task for callback handling
                    from .task_suggestion_handler import store_detected_task
                    store_detected_task(
                        chat_id=event.chat_id,
                        message_id=message.message_id,
                        task_data={
                            "detected_task": result["task_description"],
                            "confidence": result["confidence"],
                            "suggested_assignee": result.get("suggested_assignee"),
                            "original_text": text,
                            "user_id": event.user_id
                        }
                    )

                    # Публикуем событие автоматического обнаружения задачи
                    auto_task_event = AutoTaskDetectedEvent(
                        chat_id=event.chat_id,
                        detected_task=result["task_description"],
                        confidence=result["confidence"],
                        source_message=message,
                        suggested_assignee=result.get("suggested_assignee")
                    )

                    await event_bus.publish(auto_task_event)

                    bot_logger.info(
                        f"Auto task detected: {result['task_description']}",
                        extra={
                            "confidence": result["confidence"],
                            "user_id": event.user_id
                        }
                    )

            except json.JSONDecodeError:
                bot_logger.warning("Failed to parse AI response as JSON")

        except Exception as e:
            bot_logger.error(f"Auto task detection error: {e}")


class ChatSummaryHandler(EventHandler):
    """
    Обработчик суммаризации чата

    Создаёт краткие резюме обсуждений
    """

    @property
    def event_types(self) -> List[str]:
        return ["chat.summary.request"]

    async def handle(self, event: Event):
        messages = event.data.get("messages", [])

        if not messages:
            return

        # Собираем текст из сообщений
        chat_text = "\n".join([
            f"{msg.from_user.first_name}: {msg.text}"
            for msg in messages if msg.text
        ])

        try:
            # Генерируем суммари с помощью AI
            prompt = f"""
Создай краткое резюме следующего обсуждения:

{chat_text}

Резюме должно включать:
1. Основные темы
2. Принятые решения
3. Задачи/действия (если есть)
4. Ключевые участники

Формат: короткие пункты с эмодзи.
"""

            response = await ai_manager.chat(
                user_message=prompt,
                system_prompt="Ты - эксперт по созданию кратких резюме обсуждений."
            )

            # TODO: Отправить суммари в чат

            bot_logger.info(
                f"Chat summary generated",
                extra={
                    "messages_count": len(messages),
                    "chat_id": event.chat_id
                }
            )

        except Exception as e:
            bot_logger.error(f"Chat summary error: {e}")


# Регистрируем обработчики при загрузке модуля
async def register_ai_handlers():
    """Регистрация AI обработчиков событий"""
    event_bus.register_handler(AutoTaskDetectionHandler())
    event_bus.register_handler(ChatSummaryHandler())
    bot_logger.info("AI event handlers registered")


# Вызываем регистрацию при импорте
import asyncio
asyncio.create_task(register_ai_handlers())
