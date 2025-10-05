"""
Планировщик для ежедневных задач
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional
import pytz

from ..services.daily_tasks_service import daily_tasks_service
from ..services.user_tasks_cache_service import user_tasks_cache_service
from ..utils.logger import bot_logger
from ..config import settings


class DailyTasksScheduler:
    """Планировщик для ежедневной отправки задач и синхронизации кэша"""
    
    def __init__(self):
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.sync_task: Optional[asyncio.Task] = None
        self.check_interval = 60  # Проверка каждые 60 секунд
        self.cache_sync_interval = 1800  # Синхронизация кэша каждые 30 минут
    
    async def start(self):
        """Запустить планировщик"""
        if self.running:
            bot_logger.warning("Daily tasks scheduler already running")
            return
        
        if not daily_tasks_service:
            bot_logger.error("Daily tasks service not initialized")
            return
        
        self.running = True
        self.task = asyncio.create_task(self._scheduler_loop())
        self.sync_task = asyncio.create_task(self._cache_sync_loop())
        bot_logger.info("Daily tasks scheduler and cache sync started")
    
    async def stop(self):
        """Остановить планировщик"""
        if not self.running:
            return
        
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        
        if self.sync_task:
            self.sync_task.cancel()
            try:
                await self.sync_task
            except asyncio.CancelledError:
                pass
        
        bot_logger.info("Daily tasks scheduler and cache sync stopped")
    
    async def _scheduler_loop(self):
        """Основной цикл планировщика"""
        last_check_date = None
        
        while self.running:
            try:
                current_time = datetime.now()
                current_date = current_time.date()
                
                # Проверяем только один раз в день
                if last_check_date != current_date:
                    await self._check_and_send_daily_tasks()
                    last_check_date = current_date
                
                # Ждем следующую проверку
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                bot_logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(self.check_interval)
    
    async def _check_and_send_daily_tasks(self):
        """Проверить и отправить ежедневные задачи админам"""
        if not daily_tasks_service:
            return
        
        admins_to_notify = []
        
        # Проверяем каждого админа
        for admin_id in settings.admin_user_id_list:
            if daily_tasks_service.should_send_now(admin_id):
                admins_to_notify.append(admin_id)
        
        if not admins_to_notify:
            return
        
        bot_logger.info(f"Sending daily tasks to {len(admins_to_notify)} admins")
        
        # Отправляем задачи
        results = {}
        for admin_id in admins_to_notify:
            results[admin_id] = await daily_tasks_service.send_daily_tasks_to_admin(admin_id)
        
        # Логируем результаты
        successful = sum(1 for success in results.values() if success)
        bot_logger.info(f"Daily tasks sent successfully to {successful}/{len(results)} admins")
    
    async def _cache_sync_loop(self):
        """Цикл синхронизации кэша пользовательских задач каждые 30 минут"""
        while self.running:
            try:
                bot_logger.info("🔄 Starting automatic cache sync for all users")
                synced_count = await user_tasks_cache_service.sync_all_users()
                
                if synced_count > 0:
                    bot_logger.info(f"✅ Automatic cache sync completed for {synced_count} users")
                else:
                    bot_logger.debug("📊 No users needed cache sync")
                
                # Ждем 30 минут до следующей синхронизации
                await asyncio.sleep(self.cache_sync_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                bot_logger.error(f"Error in cache sync loop: {e}")
                # При ошибке ждем 5 минут и пробуем снова
                await asyncio.sleep(300)
    
    def is_running(self) -> bool:
        """Проверить, запущен ли планировщик"""
        return self.running


# Глобальный экземпляр планировщика
scheduler = DailyTasksScheduler()
