"""
Event Bus - центральная система событий для reactive архитектуры

Позволяет модулям реагировать на события без жёсткой связанности

FIXES (2026-01-20):
- Added TTL-based event history cleanup to prevent memory leak
- Added background task tracking for graceful shutdown
- Reduced max_history from 1000 to 100 (sufficient for debugging)
"""
import asyncio
from typing import Dict, List, Callable, Any, Optional, Type, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from enum import Enum
import weakref

from ...utils.logger import bot_logger


class EventPriority(Enum):
    """Приоритет обработки событий"""
    CRITICAL = 0   # Критические события (безопасность, ошибки)
    HIGH = 1       # Высокий приоритет (AI обработка, уведомления)
    NORMAL = 2     # Обычные события (логирование, статистика)
    LOW = 3        # Низкий приоритет (аналитика, кэш)


@dataclass
class Event:
    """Базовый класс события"""
    event_type: str
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    user_id: Optional[int] = None
    chat_id: Optional[int] = None
    priority: EventPriority = EventPriority.NORMAL
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Автоматическое логирование события"""
        bot_logger.debug(
            f"Event created: {self.event_type}",
            extra={
                "user_id": self.user_id,
                "chat_id": self.chat_id,
                "priority": self.priority.name
            }
        )


class EventHandler(ABC):
    """Абстрактный обработчик событий"""

    @property
    @abstractmethod
    def event_types(self) -> List[str]:
        """Типы событий которые обрабатывает этот handler"""
        pass

    @property
    def priority(self) -> EventPriority:
        """Приоритет обработчика (по умолчанию NORMAL)"""
        return EventPriority.NORMAL

    @abstractmethod
    async def handle(self, event: Event) -> Any:
        """Обработка события"""
        pass

    async def on_error(self, event: Event, error: Exception):
        """Обработка ошибок (можно переопределить)"""
        bot_logger.error(
            f"Event handler error: {error}",
            extra={
                "handler": self.__class__.__name__,
                "event_type": event.event_type,
                "error": str(error)
            }
        )


class EventBus:
    """
    Event Bus - центральная шина событий

    Singleton для управления всеми событиями в приложении

    FIXES (2026-01-20):
    - Instance-level attributes instead of class-level
    - TTL-based cleanup (1 hour default)
    - Background task tracking for graceful shutdown
    - Reduced max_history to 100
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # Initialize instance attributes here (not class-level!)
            cls._instance._handlers: Dict[str, List[EventHandler]] = {}
            cls._instance._middleware: List[Callable] = []
            cls._instance._event_history: List[Event] = []
            cls._instance._max_history: int = 100  # Reduced from 1000
            cls._instance._event_ttl_hours: int = 1  # Events older than 1 hour are cleared
            cls._instance._background_tasks: Set[asyncio.Task] = set()
            cls._instance._cleanup_task: Optional[asyncio.Task] = None
        return cls._instance

    async def start_cleanup_loop(self, interval_minutes: int = 30):
        """Start periodic cleanup of old events (call on bot startup)"""
        if self._cleanup_task is not None:
            return  # Already running

        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(interval_minutes * 60)
                    self._cleanup_old_events()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    bot_logger.error(f"Event cleanup error: {e}")

        self._cleanup_task = asyncio.create_task(cleanup_loop())
        bot_logger.info(f"Event cleanup loop started (interval: {interval_minutes}min)")

    async def stop_cleanup_loop(self):
        """Stop cleanup loop (call on bot shutdown)"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

    def _cleanup_old_events(self):
        """Remove events older than TTL"""
        if not self._event_history:
            return

        cutoff = datetime.now() - timedelta(hours=self._event_ttl_hours)
        old_count = len(self._event_history)
        self._event_history = [e for e in self._event_history if e.timestamp > cutoff]
        removed = old_count - len(self._event_history)

        if removed > 0:
            bot_logger.debug(f"Cleaned up {removed} old events (TTL: {self._event_ttl_hours}h)")

    async def wait_for_background_tasks(self, timeout: float = 5.0):
        """Wait for all background tasks to complete (call on shutdown)"""
        if not self._background_tasks:
            return

        bot_logger.info(f"Waiting for {len(self._background_tasks)} background tasks...")
        try:
            await asyncio.wait_for(
                asyncio.gather(*self._background_tasks, return_exceptions=True),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            bot_logger.warning(f"Background tasks timeout after {timeout}s")

    def register_handler(self, handler: EventHandler):
        """Регистрация обработчика событий"""
        for event_type in handler.event_types:
            if event_type not in self._handlers:
                self._handlers[event_type] = []

            self._handlers[event_type].append(handler)
            # Сортируем по приоритету
            self._handlers[event_type].sort(key=lambda h: h.priority.value)

        bot_logger.info(
            f"Registered event handler: {handler.__class__.__name__}",
            extra={"event_types": handler.event_types}
        )

    def unregister_handler(self, handler: EventHandler):
        """Удаление обработчика"""
        for event_type in handler.event_types:
            if event_type in self._handlers:
                self._handlers[event_type].remove(handler)

    def add_middleware(self, middleware: Callable):
        """
        Добавление middleware для событий
        Middleware вызывается перед обработкой события
        """
        self._middleware.append(middleware)
        bot_logger.info(f"Added event middleware: {middleware.__name__}")

    async def publish(self, event: Event, wait: bool = False) -> List[Any]:
        """
        Публикация события

        Args:
            event: Событие для публикации
            wait: Ждать выполнения всех обработчиков (по умолчанию False)

        Returns:
            Список результатов от обработчиков (если wait=True)
        """
        # FIX (2026-01-20): Add to history with size limit AND TTL cleanup
        self._event_history.append(event)
        # Size-based cleanup (immediate)
        while len(self._event_history) > self._max_history:
            self._event_history.pop(0)
        # TTL-based cleanup runs periodically via start_cleanup_loop()

        # Применяем middleware
        for middleware in self._middleware:
            try:
                event = await middleware(event) if asyncio.iscoroutinefunction(middleware) else middleware(event)
                if event is None:  # Middleware может отменить событие
                    bot_logger.debug(f"Event {event.event_type} cancelled by middleware")
                    return []
            except Exception as e:
                bot_logger.error(f"Event middleware error: {e}")

        # Получаем обработчики
        handlers = self._handlers.get(event.event_type, [])

        if not handlers:
            bot_logger.debug(f"No handlers for event: {event.event_type}")
            return []

        bot_logger.info(
            f"Publishing event: {event.event_type}",
            extra={
                "handlers_count": len(handlers),
                "priority": event.priority.name
            }
        )

        # Создаём задачи для обработчиков
        tasks = []
        for handler in handlers:
            task = self._execute_handler(handler, event)
            tasks.append(task)

        if wait:
            # Ждём выполнения всех обработчиков
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return results
        else:
            # FIX (2026-01-20): Track background tasks for graceful shutdown
            task = asyncio.create_task(asyncio.gather(*tasks, return_exceptions=True))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
            return []

    async def _execute_handler(self, handler: EventHandler, event: Event):
        """Выполнение обработчика с обработкой ошибок"""
        try:
            result = await handler.handle(event)
            bot_logger.debug(
                f"Handler executed: {handler.__class__.__name__}",
                extra={"event_type": event.event_type}
            )
            return result
        except Exception as e:
            bot_logger.error(
                f"Handler execution failed: {handler.__class__.__name__}",
                extra={
                    "event_type": event.event_type,
                    "error": str(e)
                }
            )
            await handler.on_error(event, e)
            return None

    def get_event_history(self, event_type: Optional[str] = None, limit: int = 100) -> List[Event]:
        """Получить историю событий"""
        if event_type:
            events = [e for e in self._event_history if e.event_type == event_type]
        else:
            events = self._event_history

        return events[-limit:] if limit else events

    def clear_history(self):
        """Очистить историю событий"""
        self._event_history.clear()
        bot_logger.info("Event history cleared")

    def get_handlers(self, event_type: str) -> List[EventHandler]:
        """Получить обработчики для типа события"""
        return self._handlers.get(event_type, [])

    @property
    def registered_event_types(self) -> List[str]:
        """Получить список всех зарегистрированных типов событий"""
        return list(self._handlers.keys())


# Глобальный экземпляр Event Bus
event_bus = EventBus()
