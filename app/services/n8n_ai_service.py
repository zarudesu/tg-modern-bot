"""
N8n AI Service - отправка сообщений на AI анализ через n8n

Бот становится "тупым" роутером:
- Минимальная фильтрация (длина, команды, rate limit)
- Всё остальное → n8n для AI анализа
- n8n возвращает результат через webhook
"""
import time
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List
from collections import defaultdict
import aiohttp

from aiogram.types import Message

from ..utils.logger import bot_logger
from ..config import settings


class ChatRateLimiter:
    """
    Rate limiter для AI запросов по чатам.

    Предотвращает перегрузку AI сервиса частыми запросами.
    """

    def __init__(self, max_per_minute: int = 10, cooldown_seconds: int = 3):
        """
        Args:
            max_per_minute: Максимум запросов на чат в минуту
            cooldown_seconds: Минимальный интервал между запросами от одного чата
        """
        self.max_per_minute = max_per_minute
        self.cooldown_seconds = cooldown_seconds
        self.chat_timestamps: Dict[int, List[float]] = defaultdict(list)
        self.last_request: Dict[int, float] = {}

    def is_allowed(self, chat_id: int) -> bool:
        """Проверить, разрешён ли запрос для чата"""
        now = time.time()

        # 1. Проверка cooldown (минимальный интервал)
        last = self.last_request.get(chat_id, 0)
        if now - last < self.cooldown_seconds:
            return False

        # 2. Проверка rate limit (запросов в минуту)
        minute_ago = now - 60
        self.chat_timestamps[chat_id] = [
            ts for ts in self.chat_timestamps[chat_id]
            if ts > minute_ago
        ]

        if len(self.chat_timestamps[chat_id]) >= self.max_per_minute:
            return False

        # Разрешаем и записываем
        self.chat_timestamps[chat_id].append(now)
        self.last_request[chat_id] = now
        return True

    def get_wait_time(self, chat_id: int) -> float:
        """Получить время ожидания до следующего разрешённого запроса"""
        now = time.time()
        last = self.last_request.get(chat_id, 0)
        cooldown_wait = max(0, self.cooldown_seconds - (now - last))
        return cooldown_wait


class N8nAIService:
    """
    Сервис для отправки сообщений в n8n на AI анализ.

    Поддерживаемые endpoints:
    - /webhooks/ai/detect-task - анализ сообщения на задачу
    - /webhooks/ai/voice-report - обработка голосового отчёта
    - /webhooks/ai/chat - общий чат с AI
    """

    # Shared session для всех запросов
    _session: Optional[aiohttp.ClientSession] = None

    # Rate limiter (singleton)
    _rate_limiter: Optional[ChatRateLimiter] = None

    def __init__(self, base_url: Optional[str] = None):
        """
        Args:
            base_url: Базовый URL n8n (например https://n8n.hhivp.com)
        """
        self.base_url = base_url or getattr(settings, 'n8n_url', None)
        self.webhook_secret = getattr(settings, 'n8n_webhook_secret', None)
        self.timeout = 30

        # Endpoints для разных типов запросов
        self.endpoints = {
            'detect_task': '/webhook/ai/detect-task',
            'voice_report': '/webhook/ai/voice-report',
            'chat': '/webhook/ai/chat',
        }

    @classmethod
    def get_rate_limiter(cls) -> ChatRateLimiter:
        """Получить singleton rate limiter"""
        if cls._rate_limiter is None:
            cls._rate_limiter = ChatRateLimiter(
                max_per_minute=10,  # 10 AI запросов на чат в минуту
                cooldown_seconds=3   # Минимум 3 секунды между запросами
            )
        return cls._rate_limiter

    @classmethod
    async def get_session(cls) -> aiohttp.ClientSession:
        """Получить или создать shared session"""
        if cls._session is None or cls._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            cls._session = aiohttp.ClientSession(timeout=timeout)
            bot_logger.debug("Created new aiohttp session for N8nAIService")
        return cls._session

    @classmethod
    async def close_session(cls):
        """Закрыть session (вызывать при shutdown бота)"""
        if cls._session and not cls._session.closed:
            await cls._session.close()
            cls._session = None
            bot_logger.info("Closed N8nAIService aiohttp session")

    def _get_headers(self) -> Dict[str, str]:
        """Получить заголовки для запроса"""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "TelegramBot/2.0-AI"
        }
        if self.webhook_secret:
            headers["X-Webhook-Secret"] = self.webhook_secret
        return headers

    async def _send_request(
        self,
        endpoint: str,
        data: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Отправить запрос в n8n.

        Returns:
            Tuple[success, response_data]
        """
        if not self.base_url:
            bot_logger.warning("N8n base URL not configured")
            return False, {"error": "N8n URL not configured"}

        url = f"{self.base_url.rstrip('/')}{endpoint}"

        try:
            session = await self.get_session()
            async with session.post(
                url,
                json=data,
                headers=self._get_headers()
            ) as response:
                response_text = await response.text()

                if response.status == 200:
                    try:
                        import json
                        result = json.loads(response_text)
                        return True, result
                    except:
                        return True, {"raw": response_text}
                else:
                    bot_logger.error(f"N8n AI request failed: {response.status} - {response_text}")
                    return False, {"error": f"HTTP {response.status}", "details": response_text}

        except asyncio.TimeoutError:
            bot_logger.error(f"N8n AI request timeout: {endpoint}")
            return False, {"error": "Timeout"}
        except aiohttp.ClientError as e:
            bot_logger.error(f"N8n AI network error: {e}")
            return False, {"error": f"Network error: {e}"}
        except Exception as e:
            bot_logger.error(f"N8n AI unexpected error: {e}")
            return False, {"error": f"Unexpected error: {e}"}

    # ==================== TASK DETECTION ====================

    def should_analyze_message(self, message: Message) -> Tuple[bool, str]:
        """
        Минимальная проверка - должно ли сообщение идти на AI анализ.

        Логика НЕ на нейронке (базовые проверки):
        - Команды - нет
        - От ботов - нет
        - Слишком короткие - нет
        - Rate limited - нет

        Returns:
            Tuple[should_analyze, reason]
        """
        # 1. Пропускаем команды
        if message.text and message.text.startswith('/'):
            return False, "command"

        # 2. Пропускаем ботов
        if message.from_user and message.from_user.is_bot:
            return False, "bot"

        # 3. Пропускаем слишком короткие (< 10 символов)
        text = message.text or message.caption or ""
        if len(text.strip()) < 10:
            return False, "too_short"

        # 4. Rate limit
        rate_limiter = self.get_rate_limiter()
        if not rate_limiter.is_allowed(message.chat.id):
            return False, "rate_limited"

        return True, "ok"

    async def analyze_message_for_task(
        self,
        message: Message,
        plane_project_id: Optional[str] = None,
        plane_project_name: Optional[str] = None
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Отправить сообщение на AI анализ для детекции задачи.

        Args:
            message: Telegram сообщение
            plane_project_id: ID проекта Plane (если чат замаплен)
            plane_project_name: Название проекта

        Returns:
            Tuple[success, result]
            result содержит: type, confidence, task_data (если задача)
        """
        # Проверяем, нужен ли анализ
        should_analyze, reason = self.should_analyze_message(message)
        if not should_analyze:
            bot_logger.debug(f"Skipping AI analysis: {reason}")
            return False, {"skipped": reason}

        # Собираем данные для n8n
        data = {
            "source": "telegram_bot",
            "event_type": "message_for_task_detection",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "message": {
                "text": message.text or message.caption or "",
                "message_id": message.message_id,
                "date": message.date.isoformat() if message.date else None,
            },
            "chat": {
                "id": message.chat.id,
                "title": message.chat.title,
                "type": message.chat.type,
            },
            "user": {
                "id": message.from_user.id,
                "name": message.from_user.full_name,
                "username": message.from_user.username,
            },
            "plane": {
                "project_id": plane_project_id,
                "project_name": plane_project_name,
            },
            "reply_to": None
        }

        # Добавляем контекст если это ответ
        if message.reply_to_message:
            data["reply_to"] = {
                "message_id": message.reply_to_message.message_id,
                "text": message.reply_to_message.text or message.reply_to_message.caption,
                "user_name": message.reply_to_message.from_user.full_name if message.reply_to_message.from_user else None,
            }

        bot_logger.info(
            f"Sending message for AI task detection",
            extra={
                "chat_id": message.chat.id,
                "message_length": len(data["message"]["text"])
            }
        )

        return await self._send_request(self.endpoints['detect_task'], data)

    # ==================== VOICE REPORT ====================

    async def process_voice_report(
        self,
        message: Message,
        voice_file_url: str,
        admin_telegram_id: int,
        admin_name: str
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Отправить голосовое сообщение на обработку в n8n.

        n8n workflow:
        1. Скачивает файл
        2. Транскрибирует через Whisper
        3. AI извлекает данные (задача, длительность, компания, исполнители)
        4. Ищет задачу в Plane
        5. Создаёт отчёт

        Args:
            message: Telegram сообщение с голосовым
            voice_file_url: URL для скачивания файла
            admin_telegram_id: ID админа
            admin_name: Имя админа

        Returns:
            Tuple[success, result]
        """
        data = {
            "source": "telegram_bot",
            "event_type": "voice_report",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "voice": {
                "file_url": voice_file_url,
                "duration": message.voice.duration if message.voice else 0,
                "file_id": message.voice.file_id if message.voice else None,
            },
            "admin": {
                "telegram_id": admin_telegram_id,
                "name": admin_name,
            },
            "chat": {
                "id": message.chat.id,
                "type": message.chat.type,
            },
            "message_id": message.message_id,
            "callback_url": f"http://rd.hhivp.com:8083/webhooks/ai/voice-result"
        }

        bot_logger.info(
            f"Sending voice for AI processing",
            extra={
                "admin_id": admin_telegram_id,
                "duration": data["voice"]["duration"]
            }
        )

        return await self._send_request(self.endpoints['voice_report'], data)

    # ==================== GENERAL CHAT ====================

    async def chat_with_ai(
        self,
        user_message: str,
        user_id: int,
        chat_id: int,
        context: Optional[List[str]] = None
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Отправить сообщение для AI чата (/ai команда).

        Args:
            user_message: Сообщение пользователя
            user_id: Telegram ID пользователя
            chat_id: ID чата
            context: Предыдущие сообщения (опционально)

        Returns:
            Tuple[success, result с ответом AI]
        """
        data = {
            "source": "telegram_bot",
            "event_type": "ai_chat",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "message": user_message,
            "user_id": user_id,
            "chat_id": chat_id,
            "context": context or [],
            "callback_url": f"http://rd.hhivp.com:8083/webhooks/ai/chat-result"
        }

        return await self._send_request(self.endpoints['chat'], data)

    # ==================== TEST ====================

    async def test_connection(self) -> Tuple[bool, str]:
        """Тест соединения с n8n"""
        if not self.base_url:
            return False, "N8n URL not configured"

        try:
            session = await self.get_session()
            async with session.get(
                f"{self.base_url}/healthz",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    return True, "n8n is healthy"
                else:
                    return False, f"n8n returned {response.status}"
        except Exception as e:
            return False, f"Connection error: {e}"


# Глобальный экземпляр
n8n_ai_service = N8nAIService()
