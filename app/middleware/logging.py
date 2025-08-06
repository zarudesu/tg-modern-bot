"""
Middleware для логирования сообщений
"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from ..database.database import get_async_session
from ..database.models import MessageLog, BotUser
from ..utils.logger import bot_logger
from sqlalchemy import select


class LoggingMiddleware(BaseMiddleware):
    """Middleware для логирования всех сообщений и действий"""
    
    def __init__(self):
        super().__init__()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Логирование событий"""
        
        # Обрабатываем только сообщения и callback query
        if isinstance(event, Message):
            await self._log_message(event, data)
        elif isinstance(event, CallbackQuery):
            await self._log_callback(event, data)
        
        # Продолжаем обработку
        try:
            return await handler(event, data)
        except Exception as e:
            # Логируем ошибки
            bot_logger.error(
                f"Handler error: {e}",
                extra={
                    "event_type": type(event).__name__,
                    "user_id": getattr(event.from_user, 'id', None),
                    "chat_id": getattr(event.chat, 'id', None) if hasattr(event, 'chat') else None
                }
            )
            raise
    
    async def _log_message(self, message: Message, data: Dict[str, Any]):
        """Логирование обычного сообщения"""
        try:
            # Определяем тип сообщения
            message_type = "text"
            text_content = message.text
            metadata = {}
            
            if message.photo:
                message_type = "photo"
                text_content = message.caption
                metadata["photo_count"] = len(message.photo)
            elif message.document:
                message_type = "document"
                text_content = message.caption
                metadata["file_name"] = message.document.file_name
                metadata["file_size"] = message.document.file_size
            elif message.video:
                message_type = "video"
                text_content = message.caption
                metadata["duration"] = message.video.duration
            elif message.audio:
                message_type = "audio"
                text_content = message.caption
                metadata["duration"] = message.audio.duration
            elif message.voice:
                message_type = "voice"
                metadata["duration"] = message.voice.duration
            elif message.sticker:
                message_type = "sticker"
                metadata["emoji"] = message.sticker.emoji
                metadata["set_name"] = message.sticker.set_name
            elif message.location:
                message_type = "location"
                metadata["latitude"] = message.location.latitude
                metadata["longitude"] = message.location.longitude
            elif message.contact:
                message_type = "contact"
                metadata["phone_number"] = message.contact.phone_number
                metadata["first_name"] = message.contact.first_name
            
            # Добавляем информацию о пересылке
            if message.forward_from:
                metadata["forwarded_from"] = message.forward_from.id
            
            # Добавляем информацию о ответе
            if message.reply_to_message:
                metadata["reply_to_message_id"] = message.reply_to_message.message_id
            
            # Используем сессию из DatabaseSessionMiddleware
            session = data.get('db_session')
            if not session:
                bot_logger.debug("No database session available for message logging")
                return
            
            # Проверяем, существует ли пользователь в базе
            user_result = await session.execute(
                select(BotUser).where(BotUser.telegram_user_id == message.from_user.id)
            )
            user_exists = user_result.scalar_one_or_none()
            
            # Если пользователь не существует, пропускаем логирование
            # (пользователь будет создан в обработчике команд)
            if not user_exists:
                bot_logger.debug(f"Skipping message log for new user {message.from_user.id}")
                return
            
            log_entry = MessageLog(
                telegram_message_id=str(message.message_id),
                telegram_user_id=message.from_user.id,
                chat_id=message.chat.id,
                chat_type=message.chat.type,
                message_type=message_type,
                text_content=text_content,
                message_metadata=metadata
            )
            
            session.add(log_entry)
            # Не делаем commit здесь - он будет в DatabaseSessionMiddleware
                
        except Exception as e:
            bot_logger.error(f"Message logging error: {e}")
    
    async def _log_callback(self, callback: CallbackQuery, data: Dict[str, Any]):
        """Логирование callback query"""
        try:
            metadata = {
                "callback_data": callback.data,
                "message_id": callback.message.message_id if callback.message else None
            }
            
            # Используем сессию из DatabaseSessionMiddleware
            session = data.get('db_session')
            if not session:
                bot_logger.debug("No database session available for callback logging")
                return
            
            # Проверяем, существует ли пользователь в базе
            user_result = await session.execute(
                select(BotUser).where(BotUser.telegram_user_id == callback.from_user.id)
            )
            user_exists = user_result.scalar_one_or_none()
            
            # Если пользователь не существует, пропускаем логирование
            if not user_exists:
                bot_logger.debug(f"Skipping callback log for new user {callback.from_user.id}")
                return
            
            log_entry = MessageLog(
                telegram_message_id=str(callback.id),  # Используем ID callback query
                telegram_user_id=callback.from_user.id,
                chat_id=callback.message.chat.id if callback.message else callback.from_user.id,
                chat_type="callback",
                message_type="callback_query",
                text_content=callback.data,
                message_metadata=metadata
            )
            
            session.add(log_entry)
            # Не делаем commit здесь - он будет в DatabaseSessionMiddleware
                
        except Exception as e:
            bot_logger.error(f"Callback logging error: {e}")


class GroupMonitoringMiddleware(BaseMiddleware):
    """Middleware для мониторинга групповых сообщений"""
    
    def __init__(self):
        super().__init__()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Мониторинг групповых сообщений"""
        
        if isinstance(event, Message) and event.chat.type in ["group", "supergroup"]:
            await self._monitor_group_message(event)
        
        return await handler(event, data)
    
    async def _monitor_group_message(self, message: Message):
        """Мониторинг сообщения в группе"""
        try:
            # Проверяем, обращаются ли к боту
            bot_mentioned = False
            bot_command = False
            
            if message.text:
                # Проверяем упоминание бота
                if message.entities:
                    for entity in message.entities:
                        if entity.type == "mention":
                            mentioned_username = message.text[entity.offset:entity.offset + entity.length]
                            if "hhivp_it_bot" in mentioned_username.lower():
                                bot_mentioned = True
                        elif entity.type == "bot_command":
                            bot_command = True
            
            # Логируем активность в группе
            bot_logger.info(
                "Group message monitored",
                extra={
                    "event_type": "group_message",
                    "chat_id": message.chat.id,
                    "chat_title": message.chat.title,
                    "user_id": message.from_user.id,
                    "username": message.from_user.username,
                    "message_type": "text" if message.text else "media",
                    "bot_mentioned": bot_mentioned,
                    "bot_command": bot_command,
                    "message_length": len(message.text) if message.text else 0
                }
            )
            
            # Дополнительное логирование для важных событий
            if bot_mentioned or bot_command:
                bot_logger.info(
                    f"Bot interaction in group {message.chat.title}: "
                    f"{'mention' if bot_mentioned else 'command'} "
                    f"from @{message.from_user.username}"
                )
                
        except Exception as e:
            bot_logger.error(f"Group monitoring error: {e}")


class PerformanceMiddleware(BaseMiddleware):
    """Middleware для мониторинга производительности"""
    
    def __init__(self):
        super().__init__()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Мониторинг производительности обработчиков"""
        
        import time
        start_time = time.time()
        
        try:
            result = await handler(event, data)
            execution_time = time.time() - start_time
            
            # Логируем медленные операции
            if execution_time > 2.0:  # Более 2 секунд
                bot_logger.warning(
                    f"Slow handler execution: {execution_time:.2f}s",
                    extra={
                        "event_type": type(event).__name__,
                        "execution_time": execution_time,
                        "user_id": getattr(event.from_user, 'id', None)
                    }
                )
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            bot_logger.error(
                f"Handler failed after {execution_time:.2f}s: {e}",
                extra={
                    "event_type": type(event).__name__,
                    "execution_time": execution_time,
                    "user_id": getattr(event.from_user, 'id', None)
                }
            )
            raise
