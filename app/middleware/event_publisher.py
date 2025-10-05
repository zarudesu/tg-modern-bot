"""
Event Publisher Middleware

Автоматически публикует события для всех входящих сообщений и callbacks
"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from ..core.events.event_bus import event_bus
from ..core.events.events import MessageReceivedEvent, CallbackQueryEvent
from ..utils.logger import bot_logger


class EventPublisherMiddleware(BaseMiddleware):
    """
    Middleware для автоматической публикации событий

    Преобразует Telegram обновления в события Event Bus
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Публикация событий перед обработкой"""

        # Публикуем событие в зависимости от типа
        if isinstance(event, Message):
            await self._publish_message_event(event)
        elif isinstance(event, CallbackQuery):
            await self._publish_callback_event(event)

        # Продолжаем обработку
        return await handler(event, data)

    async def _publish_message_event(self, message: Message):
        """Публикация события сообщения"""
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
            elif message.sticker:
                message_type = "sticker"

            # Создаём событие
            event = MessageReceivedEvent(
                message=message,
                user_id=message.from_user.id,
                chat_id=message.chat.id,
                text=message.text or message.caption,
                message_type=message_type,
                metadata={
                    "chat_type": message.chat.type,
                    "from_username": message.from_user.username,
                    "from_full_name": message.from_user.full_name
                }
            )

            # Публикуем асинхронно
            await event_bus.publish(event, wait=False)

        except Exception as e:
            bot_logger.error(f"Failed to publish message event: {e}")

    async def _publish_callback_event(self, callback: CallbackQuery):
        """Публикация события callback"""
        try:
            event = CallbackQueryEvent(
                callback=callback,
                user_id=callback.from_user.id,
                callback_data=callback.data,
                metadata={
                    "message_id": callback.message.message_id if callback.message else None,
                    "from_username": callback.from_user.username
                }
            )

            # Публикуем асинхронно
            await event_bus.publish(event, wait=False)

        except Exception as e:
            bot_logger.error(f"Failed to publish callback event: {e}")
