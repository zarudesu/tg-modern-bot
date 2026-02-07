"""
Redis service wrapper with fallback to in-memory dict.

Provides async JSON get/set/delete/exists operations.
Falls back to plain dict if Redis is unavailable.
"""

import json
from typing import Any, Optional

import redis.asyncio as aioredis

from ..utils.logger import bot_logger


class RedisService:
    """Async Redis wrapper with in-memory fallback."""

    DEFAULT_TTL = 900  # 15 min

    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None
        self._fallback: dict[str, Any] = {}
        self._connected = False

    async def connect(self, redis_url: str) -> None:
        """Connect to Redis. Falls back to in-memory on failure."""
        try:
            self._redis = aioredis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            await self._redis.ping()
            self._connected = True
            bot_logger.info("Redis connected")
        except Exception as e:
            bot_logger.warning(f"Redis unavailable, using in-memory fallback: {e}")
            self._redis = None
            self._connected = False

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.aclose()
            self._redis = None
            self._connected = False
            bot_logger.info("Redis connection closed")

    @property
    def is_connected(self) -> bool:
        return self._connected

    # --- Core operations ---

    async def get_json(self, key: str) -> Optional[Any]:
        """Get parsed JSON value by key."""
        if self._redis:
            try:
                raw = await self._redis.get(key)
                return json.loads(raw) if raw else None
            except Exception as e:
                bot_logger.warning(f"Redis GET error for {key}: {e}")
        return self._fallback.get(key)

    async def set_json(self, key: str, data: Any, ttl: int = DEFAULT_TTL) -> None:
        """Set JSON value with TTL (seconds)."""
        if self._redis:
            try:
                await self._redis.set(key, json.dumps(data, ensure_ascii=False, default=str), ex=ttl)
                return
            except Exception as e:
                bot_logger.warning(f"Redis SET error for {key}: {e}")
        self._fallback[key] = data

    async def delete(self, key: str) -> None:
        """Delete key."""
        if self._redis:
            try:
                await self._redis.delete(key)
                return
            except Exception as e:
                bot_logger.warning(f"Redis DELETE error for {key}: {e}")
        self._fallback.pop(key, None)

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        if self._redis:
            try:
                return bool(await self._redis.exists(key))
            except Exception as e:
                bot_logger.warning(f"Redis EXISTS error for {key}: {e}")
        return key in self._fallback


# Global singleton
redis_service = RedisService()
