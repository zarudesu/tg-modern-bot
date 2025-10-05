"""
Мониторинг сообщений в чатах

Читает все сообщения и публикует события для обработки
"""
from aiogram import Router, F
from aiogram.types import Message
from typing import List

from ...core.events.event_bus import event_bus, EventHandler, Event
from ...core.events.events import MessageReceivedEvent
from ...utils.logger import bot_logger

router = Router()


@router.message(F.chat.type.in_(["group", "supergroup"]))
async def monitor_group_message(message: Message):
    """
    Мониторинг сообщений в группах

    Читает ВСЕ сообщения в группах и публикует события
    """
    try:
        # Определяем тип сообщения
        message_type = "text"
        if message.photo:
            message_type = "photo"
        elif message.document:
            message_type = "document"
        elif message.voice:
            message_type = "voice"
        elif message.video:
            message_type = "video"

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

    except Exception as e:
        bot_logger.error(f"Message monitoring error: {e}")


class MessageContextBuilder(EventHandler):
    """
    Обработчик для построения контекста из сообщений

    Сохраняет последние N сообщений для каждого чата
    """

    def __init__(self, max_messages: int = 50):
        self.max_messages = max_messages
        self.chat_contexts: dict = {}  # chat_id -> List[Message]

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

        # Инициализируем контекст для чата если нужно
        if chat_id not in self.chat_contexts:
            self.chat_contexts[chat_id] = []

        # Добавляем сообщение в контекст
        self.chat_contexts[chat_id].append(message)

        # Ограничиваем размер контекста
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
        """Получить контекст чата (последние N сообщений)"""
        context = self.chat_contexts.get(chat_id, [])
        return context[-limit:] if limit else context

    def clear_context(self, chat_id: int):
        """Очистить контекст чата"""
        if chat_id in self.chat_contexts:
            del self.chat_contexts[chat_id]


# Глобальный экземпляр для доступа из других модулей
message_context_builder = MessageContextBuilder()

# Регистрируем обработчик
event_bus.register_handler(message_context_builder)
