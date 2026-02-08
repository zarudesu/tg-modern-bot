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
        self.plane_analysis_task: Optional[asyncio.Task] = None
        self.plane_analysis_hour = 9  # 09:00 MSK
        self._last_plane_analysis_date = None
        self.weekly_audit_task: Optional[asyncio.Task] = None
        self._last_weekly_audit_date = None
        self.reconciliation_task: Optional[asyncio.Task] = None
        self.reconciliation_hour = 18  # 18:00 MSK
        self._last_reconciliation_date = None
    
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
        self.plane_analysis_task = asyncio.create_task(self._plane_analysis_loop())
        self.weekly_audit_task = asyncio.create_task(self._weekly_audit_loop())
        self.reconciliation_task = asyncio.create_task(self._reconciliation_loop())
        bot_logger.info("Daily tasks scheduler, reminders, plane analysis, weekly audit and reconciliation started")
    
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

        if self.plane_analysis_task:
            self.plane_analysis_task.cancel()
            try:
                await self.plane_analysis_task
            except asyncio.CancelledError:
                pass

        if self.weekly_audit_task:
            self.weekly_audit_task.cancel()
            try:
                await self.weekly_audit_task
            except asyncio.CancelledError:
                pass

        if self.reconciliation_task:
            self.reconciliation_task.cancel()
            try:
                await self.reconciliation_task
            except asyncio.CancelledError:
                pass

        bot_logger.info("All scheduler tasks stopped")
    
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

    async def _plane_analysis_loop(self):
        """Daily Plane analysis at 09:00 MSK."""
        tz = pytz.timezone(settings.daily_tasks_timezone)

        while self.running:
            try:
                now = datetime.now(tz)
                today = now.date()

                if (
                    now.hour == self.plane_analysis_hour
                    and self._last_plane_analysis_date != today
                ):
                    self._last_plane_analysis_date = today
                    await self._run_plane_analysis()

                await asyncio.sleep(60)

            except asyncio.CancelledError:
                break
            except Exception as e:
                bot_logger.error(f"Error in plane analysis loop: {e}")
                await asyncio.sleep(300)

    async def _run_plane_analysis(self):
        """Fetch open issues and post AI summary to admin chat."""
        from ..integrations.plane import plane_api
        from ..core.ai.ai_manager import ai_manager

        if not plane_api.configured:
            return

        chat_id = settings.plane_chat_id
        topic_id = settings.plane_topic_id

        if not chat_id:
            bot_logger.warning("plane_chat_id not set, skipping scheduled analysis")
            return

        try:
            projects = await plane_api.get_all_projects()
            if not projects:
                return

            import aiohttp
            now = datetime.now(timezone.utc)
            stale_threshold = now - timedelta(days=7)
            report_parts = []
            total_open = 0
            total_stale = 0

            for proj in projects:
                pid = proj['id']
                pname = proj.get('identifier') or proj.get('name', '?')

                try:
                    async with aiohttp.ClientSession() as session:
                        tasks = await plane_api._tasks_manager._get_project_issues(
                            session, pid, assigned_only=False
                        )
                except Exception:
                    continue

                if not tasks:
                    continue

                total_open += len(tasks)
                stale = []
                no_assignee = []
                for t in tasks:
                    if t.updated_at:
                        try:
                            updated = datetime.fromisoformat(t.updated_at.replace('Z', '+00:00'))
                            if updated < stale_threshold:
                                stale.append(t)
                        except (ValueError, TypeError):
                            pass
                    if not t.assignee_names:
                        no_assignee.append(t)

                total_stale += len(stale)

                part = f"📂 {pname}: {len(tasks)} открытых"
                if stale:
                    part += f", ⚠️ {len(stale)} застряли"
                if no_assignee:
                    part += f", ❓ {len(no_assignee)} без исполнителя"
                report_parts.append(part)

            if not report_parts:
                return

            summary_text = (
                f"📊 <b>Ежедневный отчёт Plane</b>\n"
                f"📋 Всего открытых: {total_open}\n"
                f"⚠️ Без движения &gt;7 дней: {total_stale}\n\n"
                + "\n".join(report_parts)
            )

            # AI analysis
            if ai_manager.providers_count > 0 and total_open > 0:
                try:
                    ai_response = await ai_manager.chat(
                        user_message=(
                            f"Ежедневный отчёт:\n{summary_text}\n\n"
                            f"Кратко (2-3 предложения): что требует внимания?"
                        ),
                        system_prompt="Ты помощник руководителя IT. Анализируй кратко."
                    )
                    if ai_response and ai_response.content:
                        summary_text += f"\n\n🤖 <b>AI:</b> {ai_response.content}"
                except Exception as e:
                    bot_logger.warning(f"Scheduled AI analysis failed: {e}")

            # Send to admin chat
            from aiogram import Bot
            from ..config import settings as cfg
            bot = Bot(token=cfg.telegram_token)
            try:
                kwargs = {"chat_id": chat_id, "text": summary_text, "parse_mode": "HTML"}
                if topic_id:
                    kwargs["message_thread_id"] = topic_id
                await bot.send_message(**kwargs)
                bot_logger.info("Scheduled Plane analysis sent")
            finally:
                await bot.session.close()

        except Exception as e:
            bot_logger.error(f"Error in scheduled plane analysis: {e}")

    async def _weekly_audit_loop(self):
        """Weekly Plane audit on Monday at 09:00 MSK."""
        tz = pytz.timezone(settings.daily_tasks_timezone)

        while self.running:
            try:
                now = datetime.now(tz)
                today = now.date()

                # Monday = 0
                if (
                    now.weekday() == 0
                    and now.hour == 9
                    and self._last_weekly_audit_date != today
                ):
                    self._last_weekly_audit_date = today
                    await self._run_weekly_audit()

                await asyncio.sleep(60)

            except asyncio.CancelledError:
                break
            except Exception as e:
                bot_logger.error(f"Error in weekly audit loop: {e}")
                await asyncio.sleep(300)

    async def _run_weekly_audit(self):
        """Execute weekly audit and send to admin chat."""
        from ..handlers.plane_audit import generate_audit_report_text
        from ..core.ai.ai_manager import ai_manager

        chat_id = settings.plane_chat_id
        topic_id = settings.plane_topic_id
        if not chat_id:
            bot_logger.warning("plane_chat_id not set, skipping weekly audit")
            return

        try:
            report = await generate_audit_report_text()
            if not report:
                return

            # AI summary
            if ai_manager.providers_count > 0:
                try:
                    ai_response = await ai_manager.chat(
                        user_message=(
                            f"Еженедельный аудит Plane:\n{report}\n\n"
                            f"Кратко (3-5 предложений): ключевые проблемы и рекомендации на неделю."
                        ),
                        system_prompt="Ты помощник руководителя IT. Кратко и конкретно."
                    )
                    if ai_response and ai_response.content:
                        report += f"\n\n🤖 <b>AI:</b> {ai_response.content}"
                except Exception as e:
                    bot_logger.warning(f"Weekly audit AI failed: {e}")

            from aiogram import Bot
            bot = Bot(token=settings.telegram_token)
            try:
                kwargs = {"chat_id": chat_id, "text": report, "parse_mode": "HTML"}
                if topic_id:
                    kwargs["message_thread_id"] = topic_id
                await bot.send_message(**kwargs)
                bot_logger.info("Weekly Plane audit sent")
            finally:
                await bot.session.close()

        except Exception as e:
            bot_logger.error(f"Error in weekly audit: {e}")

    async def _reconciliation_loop(self):
        """Daily chat reconciliation at 18:00 MSK."""
        tz = pytz.timezone(settings.daily_tasks_timezone)

        while self.running:
            try:
                now = datetime.now(tz)
                today = now.date()

                if (
                    now.hour == self.reconciliation_hour
                    and self._last_reconciliation_date != today
                ):
                    self._last_reconciliation_date = today
                    await self._run_reconciliation()

                await asyncio.sleep(60)

            except asyncio.CancelledError:
                break
            except Exception as e:
                bot_logger.error(f"Error in reconciliation loop: {e}")
                await asyncio.sleep(300)

    async def _run_reconciliation(self):
        """Run daily chat reconciliation and send summary to admins."""
        from ..modules.reconciliation.reconciliation_service import (
            ReconciliationService,
            serialize_item,
        )

        try:
            service = ReconciliationService()
            items = await service.run()

            if not items:
                bot_logger.info("Scheduled reconciliation: no incidents found")
                return

            serialized = [serialize_item(i) for i in items]

            # Format summary
            from ..modules.reconciliation.router import _format_summary
            summary = _format_summary(serialized)
            if len(summary) > 4000:
                summary = summary[:3950] + "\n\n<i>...обрезано</i>"

            summary += "\n\n<i>Запустите /plane_reconcile для действий</i>"

            # Send to admins
            from aiogram import Bot
            bot = Bot(token=settings.telegram_token)
            try:
                for admin_id in settings.admin_user_id_list:
                    try:
                        await bot.send_message(
                            chat_id=admin_id,
                            text=summary,
                            parse_mode="HTML",
                        )
                    except Exception as e:
                        bot_logger.warning(
                            f"Failed to send reconciliation to admin {admin_id}: {e}"
                        )
                bot_logger.info(
                    f"Scheduled reconciliation sent: {len(items)} incidents"
                )
            finally:
                await bot.session.close()

        except Exception as e:
            bot_logger.error(f"Error in scheduled reconciliation: {e}")

    def is_running(self) -> bool:
        """Проверить, запущен ли планировщик"""
        return self.running


# Глобальный экземпляр планировщика
scheduler = DailyTasksScheduler()
