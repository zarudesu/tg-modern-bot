"""
Базовые типы плагинов для общих задач
"""
from abc import abstractmethod
from typing import Optional, List
from aiogram.types import Message, CallbackQuery

from .plugin_manager import Plugin
from ..events.event_bus import Event, EventHandler
from ..events.events import MessageReceivedEvent, CallbackQueryEvent, AIResponseEvent


class MessagePlugin(Plugin):
    """
    Плагин для обработки сообщений

    Автоматически регистрирует обработчик MessageReceivedEvent
    """

    async def on_load(self):
        """Регистрация обработчика сообщений"""
        handler = MessagePluginHandler(self)
        self.register_event_handler(handler)

    @abstractmethod
    async def process_message(self, message: Message, event: MessageReceivedEvent) -> Optional[str]:
        """
        Обработка сообщения

        Args:
            message: Telegram сообщение
            event: Событие получения сообщения

        Returns:
            Текст ответа или None
        """
        pass

    async def should_process(self, message: Message) -> bool:
        """
        Проверка, должен ли плагин обрабатывать сообщение
        По умолчанию - обрабатывает все сообщения
        """
        return True


class MessagePluginHandler(EventHandler):
    """Обработчик событий для MessagePlugin"""

    def __init__(self, plugin: MessagePlugin):
        self.plugin = plugin

    @property
    def event_types(self) -> List[str]:
        return ["message.received"]

    async def handle(self, event: Event):
        if not isinstance(event, MessageReceivedEvent):
            return

        message = event.data.get("message")
        if not message:
            return

        # Проверяем, должен ли плагин обрабатывать это сообщение
        if not await self.plugin.should_process(message):
            return

        # Обрабатываем сообщение
        response = await self.plugin.process_message(message, event)

        # Если есть ответ, отправляем его
        if response:
            await message.reply(response)


class CallbackPlugin(Plugin):
    """
    Плагин для обработки callback query (кнопки)

    Автоматически регистрирует обработчик CallbackQueryEvent
    """

    async def on_load(self):
        """Регистрация обработчика callback"""
        handler = CallbackPluginHandler(self)
        self.register_event_handler(handler)

    @abstractmethod
    async def process_callback(self, callback: CallbackQuery, event: CallbackQueryEvent) -> Optional[str]:
        """
        Обработка callback query

        Args:
            callback: Telegram callback query
            event: Событие callback query

        Returns:
            Текст ответа или None
        """
        pass

    async def should_process(self, callback: CallbackQuery) -> bool:
        """
        Проверка, должен ли плагин обрабатывать callback
        По умолчанию - обрабатывает все callbacks
        """
        return True


class CallbackPluginHandler(EventHandler):
    """Обработчик событий для CallbackPlugin"""

    def __init__(self, plugin: CallbackPlugin):
        self.plugin = plugin

    @property
    def event_types(self) -> List[str]:
        return ["callback.query"]

    async def handle(self, event: Event):
        if not isinstance(event, CallbackQueryEvent):
            return

        callback = event.data.get("callback")
        if not callback:
            return

        # Проверяем, должен ли плагин обрабатывать этот callback
        if not await self.plugin.should_process(callback):
            return

        # Обрабатываем callback
        response = await self.plugin.process_callback(callback, event)

        # Если есть ответ, показываем его
        if response:
            await callback.answer(response, show_alert=True)


class AIPlugin(Plugin):
    """
    Плагин для AI функциональности

    Автоматически регистрирует обработчики AI событий
    """

    async def on_load(self):
        """Регистрация AI обработчиков"""
        handler = AIPluginHandler(self)
        self.register_event_handler(handler)

    @abstractmethod
    async def process_ai_response(self, response: str, event: AIResponseEvent) -> Optional[dict]:
        """
        Обработка ответа AI

        Args:
            response: Ответ от AI
            event: Событие AI ответа

        Returns:
            Дополнительные данные или None
        """
        pass


class AIPluginHandler(EventHandler):
    """Обработчик событий для AIPlugin"""

    def __init__(self, plugin: AIPlugin):
        self.plugin = plugin

    @property
    def event_types(self) -> List[str]:
        return ["ai.response"]

    async def handle(self, event: Event):
        if not isinstance(event, AIResponseEvent):
            return

        response = event.data.get("response")
        if not response:
            return

        # Обрабатываем AI ответ
        await self.plugin.process_ai_response(response, event)
