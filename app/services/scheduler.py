"""
Планировщик для ежедневных задач
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
import pytz

from ..services.daily_tasks_service import daily_tasks_service
# CACHE DISABLED: user_tasks_cache_service removed - using direct Plane API calls
from ..services.task_reports_service import task_reports_service
from ..utils.logger import bot_logger
from ..config import settings
from ..database.database import get_async_session


class DailyTasksScheduler:
    """Планировщик для ежедневной отправки задач и синхронизации кэша"""
    
    def __init__(self):
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.sync_task: Optional[asyncio.Task] = None
        self.reminder_task: Optional[asyncio.Task] = None
        self.check_interval = 60  # Проверка каждые 60 секунд
        self.cache_sync_interval = 1800  # Синхронизация кэша каждые 30 минут
        self.reminder_interval = 1800  # Проверка напоминаний каждые 30 минут
    
    async def start(self):
        """Запустить планировщик"""
        if self.running:
            bot_logger.warning("Daily tasks scheduler already running")
            return

        self.running = True
        self.task = asyncio.create_task(self._scheduler_loop())
        # CACHE DISABLED: Direct API calls instead (rate limit 600/min)
        # self.sync_task = asyncio.create_task(self._cache_sync_loop())
        self.reminder_task = asyncio.create_task(self._reminders_loop())
        bot_logger.info("Daily tasks scheduler and task reminders started (cache sync disabled)")
    
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

        if self.reminder_task:
            self.reminder_task.cancel()
            try:
                await self.reminder_task
            except asyncio.CancelledError:
                pass

        bot_logger.info("Daily tasks scheduler, cache sync and task reminders stopped")
    
    async def _scheduler_loop(self):
        """Основной цикл планировщика"""
        last_check_date = None

        while self.running:
            try:
                # Проверяем наличие daily_tasks_service
                if not daily_tasks_service:
                    bot_logger.debug("Daily tasks service not initialized yet, waiting...")
                    await asyncio.sleep(self.check_interval)
                    continue

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

    async def _reminders_loop(self):
        """Цикл проверки и отправки напоминаний об отчётах каждые 30 минут"""
        from aiogram import Bot
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        while self.running:
            try:
                bot_logger.info("🔔 Starting task reports reminder check")

                # Получаем бота из daily_tasks_service (он уже инициализирован)
                if not daily_tasks_service or not daily_tasks_service.bot_instance:
                    bot_logger.debug("Daily tasks service or bot instance not initialized yet, waiting...")
                    await asyncio.sleep(self.reminder_interval)
                    continue

                bot = daily_tasks_service.bot_instance

                # Получаем pending отчёты
                async for session in get_async_session():
                    pending_reports = await task_reports_service.get_pending_reports(session)

                    if not pending_reports:
                        bot_logger.debug("📊 No pending task reports need reminders")
                        break

                    bot_logger.info(f"📨 Found {len(pending_reports)} pending task reports")

                    for report in pending_reports:
                        try:
                            hours_elapsed = report.hours_since_closed

                            # Определяем уровень напоминания
                            reminder_level = 0
                            urgency_emoji = "💬"
                            urgency_text = "Напоминание"

                            if hours_elapsed >= 6:
                                reminder_level = 3
                                urgency_emoji = "🚨"
                                urgency_text = "КРИТИЧНО"
                            elif hours_elapsed >= 3:
                                reminder_level = 2
                                urgency_emoji = "⚠️"
                                urgency_text = "СРОЧНО"
                            elif hours_elapsed >= 1:
                                reminder_level = 1
                                urgency_emoji = "⏰"
                                urgency_text = "Напоминание"
                            else:
                                # Ещё не прошёл 1 час - пропускаем
                                continue

                            # Проверяем - не отправляли ли недавно напоминание
                            if report.last_reminder_at:
                                time_since_reminder = (datetime.now(timezone.utc) - report.last_reminder_at).total_seconds() / 60
                                if time_since_reminder < 25:  # Минимум 25 минут между напоминаниями
                                    bot_logger.debug(
                                        f"⏭️ Skipping reminder for TaskReport #{report.id} "
                                        f"(last reminder {time_since_reminder:.0f}min ago)"
                                    )
                                    continue

                            # Формируем сообщение
                            hours_str = f"{hours_elapsed:.1f}" if hours_elapsed < 2 else f"{int(hours_elapsed)}"

                            message_text = (
                                f"{urgency_emoji} **{urgency_text}\\!** Требуется отчёт о задаче\n\n"
                                f"**Задача:** \\#{report.plane_sequence_id}\n"
                                f"**Название:** {report.task_title or 'Не указано'}\n"
                                f"**Закрыто:** {hours_str} ч назад\n"
                                f"**Напоминаний:** {report.reminder_count + 1}"
                            )

                            # Кнопка
                            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(
                                    text="📝 Заполнить отчёт",
                                    callback_data=f"fill_report:{report.id}"
                                )]
                            ])

                            # Кому отправлять
                            admin_to_notify = report.closed_by_telegram_id

                            # Если 6+ часов - уведомляем ВСЕХ админов
                            if reminder_level >= 3:
                                admins_list = settings.admin_user_id_list
                            else:
                                admins_list = [admin_to_notify] if admin_to_notify else settings.admin_user_id_list

                            # Отправляем напоминание
                            sent_count = 0
                            for admin_id in admins_list:
                                try:
                                    await bot.send_message(
                                        chat_id=admin_id,
                                        text=message_text,
                                        reply_markup=keyboard,
                                        parse_mode="MarkdownV2"
                                    )
                                    sent_count += 1
                                except Exception as e:
                                    bot_logger.warning(f"⚠️ Failed to send reminder to admin {admin_id}: {e}")

                            if sent_count > 0:
                                # Обновляем статистику напоминаний
                                await task_reports_service.update_reminder_sent(
                                    session=session,
                                    task_report_id=report.id,
                                    reminder_level=reminder_level
                                )

                                bot_logger.info(
                                    f"✅ Sent reminder for TaskReport #{report.id} "
                                    f"(level {reminder_level}, {sent_count} admins)"
                                )

                        except Exception as e:
                            bot_logger.error(f"❌ Error sending reminder for TaskReport #{report.id}: {e}")

                    # Выходим из цикла async for
                    break

                # Ждём 30 минут до следующей проверки
                await asyncio.sleep(self.reminder_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                bot_logger.error(f"Error in reminders loop: {e}")
                import traceback
                bot_logger.error(traceback.format_exc())
                # При ошибке ждем 5 минут и пробуем снова
                await asyncio.sleep(300)

    def is_running(self) -> bool:
        """Проверить, запущен ли планировщик"""
        return self.running


# Глобальный экземпляр планировщика
scheduler = DailyTasksScheduler()
