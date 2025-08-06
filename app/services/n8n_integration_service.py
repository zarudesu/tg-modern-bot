"""
Сервис для интеграции с n8n
"""
import json
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
import aiohttp
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.work_journal_models import WorkJournalEntry
from ..utils.work_journal_constants import N8nSyncStatus
from ..utils.logger import bot_logger
from ..config import settings


class N8nIntegrationService:
    """Сервис для интеграции с n8n webhook"""
    
    def __init__(self, webhook_url: Optional[str] = None, webhook_secret: Optional[str] = None):
        self.webhook_url = webhook_url or getattr(settings, 'n8n_webhook_url', None)
        self.webhook_secret = webhook_secret or getattr(settings, 'n8n_webhook_secret', None)
        self.timeout = 30  # 30 секунд таймаут
        self.max_retries = 3
    
    def _prepare_webhook_data(self, entry: WorkJournalEntry, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Подготовить данные для отправки в n8n webhook"""
        
        # Парсим исполнителей из JSON
        try:
            import json
            workers = json.loads(entry.worker_names)
        except (json.JSONDecodeError, TypeError):
            workers = [entry.worker_names] if entry.worker_names else ["Не указан"]
        
        # Конвертируем время в минуты для поля duration
        from ..utils.duration_parser import format_duration_for_n8n
        duration_minutes = format_duration_for_n8n(entry.work_duration or "0")
        
        return {
            "source": "telegram_bot",
            "event_type": "work_journal_entry",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": {
                "entry_id": entry.id,
                "user": {
                    "telegram_id": entry.telegram_user_id,
                    "email": entry.user_email,
                    "first_name": user_data.get("first_name"),
                    "username": user_data.get("username")
                },
                "work_entry": {
                    "date": entry.work_date.isoformat(),
                    "company": entry.company,
                    "duration": duration_minutes,  # Теперь числовое значение в минутах
                    "duration_text": entry.work_duration,  # Оригинальный текст для справки
                    "description": entry.work_description,
                    "is_travel": entry.is_travel,
                    "workers": workers,  # Теперь массив исполнителей
                    "workers_count": len(workers)
                },
                "creator": {
                    "telegram_id": entry.created_by_user_id,
                    "name": entry.created_by_name
                },
                "metadata": {
                    "created_at": entry.created_at.isoformat(),
                    "sync_attempts": entry.n8n_sync_attempts,
                    "bot_version": "1.1.2"  # Обновили версию
                }
            }
        }
    
    async def send_work_entry(
        self, 
        entry: WorkJournalEntry, 
        user_data: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        Отправить запись в n8n webhook
        
        Returns:
            Tuple[bool, Optional[str]]: (success, error_message)
        """
        
        if not self.webhook_url:
            bot_logger.warning("N8n webhook URL not configured")
            return False, "N8n webhook URL not configured"
        
        try:
            # Подготавливаем данные
            webhook_data = self._prepare_webhook_data(entry, user_data)
            
            # Подготавливаем заголовки
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "TelegramBot/1.0"
            }
            
            if self.webhook_secret:
                headers["X-Webhook-Secret"] = self.webhook_secret
            
            # Отправляем запрос
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(
                    self.webhook_url,
                    json=webhook_data,
                    headers=headers
                ) as response:
                    
                    response_text = await response.text()
                    
                    if response.status == 200:
                        bot_logger.info(f"Successfully sent work entry {entry.id} to n8n")
                        return True, None
                    else:
                        error_msg = f"n8n returned status {response.status}: {response_text}"
                        bot_logger.error(f"Failed to send work entry {entry.id} to n8n: {error_msg}")
                        return False, error_msg
                        
        except asyncio.TimeoutError:
            error_msg = f"Timeout sending to n8n after {self.timeout}s"
            bot_logger.error(f"Timeout sending work entry {entry.id} to n8n")
            return False, error_msg
            
        except aiohttp.ClientError as e:
            error_msg = f"Network error: {str(e)}"
            bot_logger.error(f"Network error sending work entry {entry.id} to n8n: {e}")
            return False, error_msg
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            bot_logger.error(f"Unexpected error sending work entry {entry.id} to n8n: {e}")
            return False, error_msg
    
    async def send_with_retry(
        self, 
        entry: WorkJournalEntry, 
        user_data: Dict[str, Any],
        session: AsyncSession
    ) -> bool:
        """
        Отправить с повторными попытками и обновлением статуса в БД
        """
        from .work_journal_service import WorkJournalService
        
        service = WorkJournalService(session)
        
        for attempt in range(self.max_retries):
            success, error_message = await self.send_work_entry(entry, user_data)
            
            if success:
                # Обновляем статус на успешный
                await service.update_n8n_sync_status(
                    entry.id, 
                    N8nSyncStatus.SUCCESS,
                    increment_attempts=True
                )
                return True
            else:
                # Обновляем статус с ошибкой
                await service.update_n8n_sync_status(
                    entry.id,
                    N8nSyncStatus.FAILED if attempt == self.max_retries - 1 else N8nSyncStatus.PENDING,
                    error_message=error_message,
                    increment_attempts=True
                )
                
                # Если не последняя попытка, ждем перед следующей
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # Экспоненциальная задержка: 1s, 2s, 4s
                    await asyncio.sleep(wait_time)
        
        bot_logger.error(f"Failed to send work entry {entry.id} to n8n after {self.max_retries} attempts")
        return False
    
    async def test_connection(self) -> Tuple[bool, str]:
        """
        Тестировать соединение с n8n webhook
        
        Returns:
            Tuple[bool, str]: (success, message)
        """
        
        if not self.webhook_url:
            return False, "N8n webhook URL not configured"
        
        try:
            # Отправляем тестовый запрос
            test_data = {
                "source": "telegram_bot",
                "event_type": "connection_test",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "data": {
                    "test": True,
                    "message": "Connection test from Telegram Bot"
                }
            }
            
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "TelegramBot/1.0"
            }
            
            if self.webhook_secret:
                headers["X-Webhook-Secret"] = self.webhook_secret
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.post(
                    self.webhook_url,
                    json=test_data,
                    headers=headers
                ) as response:
                    
                    if response.status == 200:
                        return True, f"Connection successful (status {response.status})"
                    else:
                        return False, f"Connection failed with status {response.status}"
                        
        except asyncio.TimeoutError:
            return False, "Connection timeout"
        except aiohttp.ClientError as e:
            return False, f"Network error: {str(e)}"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"


async def process_pending_entries(session: AsyncSession) -> int:
    """
    Фоновая задача для обработки записей, ожидающих синхронизации
    
    Returns:
        int: Количество успешно обработанных записей
    """
    from .work_journal_service import WorkJournalService
    from ..database.models import BotUser
    from sqlalchemy import select
    
    try:
        service = WorkJournalService(session)
        n8n_service = N8nIntegrationService()
        
        # Получаем записи, ожидающие синхронизации
        pending_entries = await service.get_pending_sync_entries()
        
        if not pending_entries:
            return 0
        
        bot_logger.info(f"Processing {len(pending_entries)} pending n8n sync entries")
        
        success_count = 0
        
        for entry in pending_entries:
            try:
                # Получаем данные пользователя
                user_result = await session.execute(
                    select(BotUser).where(BotUser.telegram_user_id == entry.telegram_user_id)
                )
                user = user_result.scalar_one_or_none()
                
                if not user:
                    bot_logger.error(f"User {entry.telegram_user_id} not found for entry {entry.id}")
                    continue
                
                user_data = {
                    "first_name": user.first_name,
                    "username": user.username
                }
                
                # Отправляем с повторными попытками
                success = await n8n_service.send_with_retry(entry, user_data, session)
                
                if success:
                    success_count += 1
                    
            except Exception as e:
                bot_logger.error(f"Error processing entry {entry.id}: {e}")
                continue
        
        bot_logger.info(f"Successfully processed {success_count}/{len(pending_entries)} entries")
        return success_count
        
    except Exception as e:
        bot_logger.error(f"Error in process_pending_entries: {e}")
        return 0
