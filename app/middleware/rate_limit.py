"""
Rate Limiting Middleware

Enforces rate limits from config.py to prevent spam and DoS.

Uses in-memory token bucket algorithm with per-user tracking.
Limits reset automatically based on configured intervals.
"""
import asyncio
from typing import Callable, Dict, Any, Awaitable, Optional
from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import dataclass, field

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from ..utils.logger import bot_logger
from ..config import settings


@dataclass
class RateLimitBucket:
    """Token bucket for rate limiting"""
    tokens: int
    last_update: datetime
    max_tokens: int
    refill_rate: float  # tokens per second


class RateLimitMiddleware(BaseMiddleware):
    """
    Middleware для ограничения частоты запросов

    Использует алгоритм token bucket для каждого пользователя.
    Настройки берутся из config.py:
    - rate_limit_default: "10/minute" - обычные пользователи
    - rate_limit_admin: "100/minute" - администраторы

    При превышении лимита пользователь получает предупреждение,
    последующие сообщения игнорируются до восстановления токенов.
    """

    def __init__(self):
        super().__init__()
        # Хранилище buckets по user_id
        self._buckets: Dict[int, RateLimitBucket] = {}
        # Пользователи которым уже показано предупреждение (чтобы не спамить)
        self._warned_users: Dict[int, datetime] = {}
        # Парсим настройки
        self._default_limit = self._parse_rate_limit(
            getattr(settings, 'rate_limit_default', '10/minute')
        )
        self._admin_limit = self._parse_rate_limit(
            getattr(settings, 'rate_limit_admin', '100/minute')
        )
        # Лок для thread-safety
        self._lock = asyncio.Lock()

        bot_logger.info(
            f"RateLimitMiddleware initialized: "
            f"default={self._default_limit}, admin={self._admin_limit}"
        )

    def _parse_rate_limit(self, limit_str: Optional[str]) -> tuple[int, float]:
        """
        Парсит строку лимита в (max_tokens, refill_rate_per_second)

        Формат: "N/period" где period = minute, hour, day
        Примеры: "10/minute", "100/hour", "1000/day"
        """
        if not limit_str:
            return (60, 1.0)  # Default: 60 per minute

        try:
            count_str, period = limit_str.split('/')
            count = int(count_str)

            if period == 'second':
                refill_rate = float(count)
            elif period == 'minute':
                refill_rate = count / 60.0
            elif period == 'hour':
                refill_rate = count / 3600.0
            elif period == 'day':
                refill_rate = count / 86400.0
            else:
                refill_rate = count / 60.0  # Default to per minute

            return (count, refill_rate)
        except Exception as e:
            bot_logger.warning(f"Failed to parse rate limit '{limit_str}': {e}, using default")
            return (60, 1.0)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Проверка rate limit перед обработкой"""

        # Только для Message и CallbackQuery
        if not isinstance(event, (Message, CallbackQuery)):
            return await handler(event, data)

        user = event.from_user
        if not user:
            return await handler(event, data)

        user_id = user.id

        # Проверяем rate limit
        is_allowed = await self._check_rate_limit(user_id)

        if not is_allowed:
            # Rate limit exceeded
            await self._handle_rate_limit_exceeded(event, user_id)
            return None  # Не вызываем handler

        return await handler(event, data)

    async def _check_rate_limit(self, user_id: int) -> bool:
        """Проверить и обновить rate limit для пользователя"""
        async with self._lock:
            now = datetime.now()

            # Получаем или создаём bucket
            if user_id not in self._buckets:
                # Определяем лимит (админ или обычный)
                is_admin = settings.is_admin(user_id)
                max_tokens, refill_rate = self._admin_limit if is_admin else self._default_limit

                self._buckets[user_id] = RateLimitBucket(
                    tokens=max_tokens,
                    last_update=now,
                    max_tokens=max_tokens,
                    refill_rate=refill_rate
                )

            bucket = self._buckets[user_id]

            # Пополняем токены на основе прошедшего времени
            elapsed = (now - bucket.last_update).total_seconds()
            new_tokens = int(elapsed * bucket.refill_rate)

            if new_tokens > 0:
                bucket.tokens = min(bucket.max_tokens, bucket.tokens + new_tokens)
                bucket.last_update = now

            # Проверяем есть ли токен
            if bucket.tokens > 0:
                bucket.tokens -= 1
                return True
            else:
                return False

    async def _handle_rate_limit_exceeded(
        self,
        event: TelegramObject,
        user_id: int
    ):
        """Обработка превышения лимита"""
        now = datetime.now()

        # Проверяем когда последний раз предупреждали (не чаще раза в минуту)
        last_warning = self._warned_users.get(user_id)
        if last_warning and (now - last_warning) < timedelta(minutes=1):
            # Молча игнорируем
            bot_logger.debug(f"Rate limit exceeded for user {user_id} (silent)")
            return

        # Отправляем предупреждение
        self._warned_users[user_id] = now

        warning_text = (
            "⚠️ *Слишком много запросов\\!*\n\n"
            "Пожалуйста, подождите немного перед следующим сообщением\\.\n"
            "Лимит восстановится автоматически\\."
        )

        try:
            if isinstance(event, Message):
                await event.reply(warning_text, parse_mode="MarkdownV2")
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    "⚠️ Слишком много запросов! Подождите немного.",
                    show_alert=True
                )
        except Exception as e:
            bot_logger.warning(f"Failed to send rate limit warning: {e}")

        bot_logger.warning(
            f"Rate limit exceeded for user {user_id}",
            extra={"user_id": user_id}
        )

    def reset_user_limit(self, user_id: int):
        """Сбросить лимит для пользователя (для админов)"""
        if user_id in self._buckets:
            bucket = self._buckets[user_id]
            bucket.tokens = bucket.max_tokens
            bucket.last_update = datetime.now()
            bot_logger.info(f"Rate limit reset for user {user_id}")

    def get_user_status(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получить статус лимита пользователя"""
        if user_id not in self._buckets:
            return None

        bucket = self._buckets[user_id]
        return {
            "tokens_remaining": bucket.tokens,
            "max_tokens": bucket.max_tokens,
            "refill_rate": bucket.refill_rate,
            "last_update": bucket.last_update.isoformat()
        }
