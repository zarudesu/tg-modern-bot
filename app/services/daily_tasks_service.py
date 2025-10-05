"""
Сервис для ежедневной отправки задач администраторам
"""
import asyncio
from datetime import datetime, time, timedelta
from typing import List, Dict, Any, Optional
import pytz
from aiogram import Bot
from aiogram.enums import ParseMode

from ..database.database import AsyncSessionLocal as async_session
from ..database.models import BotUser
from ..database.daily_tasks_models import AdminDailyTasksSettings, DailyTasksLog
from sqlalchemy import select, insert, update, delete
from sqlalchemy.exc import NoResultFound
from ..integrations.plane import plane_api, PlaneTask
from ..utils.logger import bot_logger
from ..utils.formatters import escape_markdown
from ..config import settings

# Глобальная переменная для доступа из модулей
daily_tasks_service = None


class DailyTasksService:
    """Сервис для ежедневной отправки списка задач админам"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.admin_settings = {}  # Кэш настроек для быстрого доступа
        bot_logger.info("Daily tasks service initialized")
    
    async def _load_admin_settings_from_db(self):
        """Загружает настройки админов из БД"""
        try:
            async with async_session() as session:
                result = await session.execute(
                    select(AdminDailyTasksSettings).where(
                        AdminDailyTasksSettings.telegram_user_id.in_(settings.admin_user_id_list)
                    )
                )
                db_settings = result.scalars().all()
                
                # Обновляем кэш
                for admin_setting in db_settings:
                    self.admin_settings[admin_setting.telegram_user_id] = admin_setting.to_dict()
                
                # Создаем настройки по умолчанию для админов, которых нет в БД
                existing_admin_ids = set(admin_setting.telegram_user_id for admin_setting in db_settings)
                for admin_id in settings.admin_user_id_list:
                    if admin_id not in existing_admin_ids:
                        await self._create_default_admin_settings(admin_id)
                
                bot_logger.info(f"Loaded settings for {len(self.admin_settings)} admins from DB")
                
        except Exception as e:
            bot_logger.error(f"Error loading admin settings from DB: {e}")
            # Fallback к настройкам по умолчанию
            self._load_default_settings()
    
    async def _create_default_admin_settings(self, admin_id: int):
        """Создает настройки по умолчанию для админа в БД"""
        try:
            default_settings = {
                'enabled': settings.daily_tasks_enabled,
                'time': settings.daily_tasks_time,
                'timezone': settings.daily_tasks_timezone,
                'include_overdue': True,
                'include_today': True,
                'include_upcoming': True,
                'group_by_project': True,
                'max_tasks_per_section': 5
            }
            
            async with async_session() as session:
                new_settings = AdminDailyTasksSettings.from_dict(default_settings, admin_id)
                session.add(new_settings)
                await session.commit()
                
                # Обновляем кэш
                self.admin_settings[admin_id] = default_settings
                
                bot_logger.info(f"Created default settings for admin {admin_id}")
                
        except Exception as e:
            bot_logger.error(f"Error creating default settings for admin {admin_id}: {e}")
            # Fallback к локальным настройкам
            self.admin_settings[admin_id] = {
                'enabled': False,
                'time': '09:00',
                'timezone': 'Europe/Moscow',
                'include_overdue': True,
                'include_today': True,
                'include_upcoming': True,
                'group_by_project': True,
                'max_tasks_per_section': 5
            }
    
    async def _save_admin_settings_to_db(self):
        """Сохраняет настройки админов в БД с детальным логированием"""
        try:
            bot_logger.info(f"🔄 Начинаем сохранение настроек для {len(self.admin_settings)} админов")
            
            async with async_session() as session:
                for admin_id, settings_data in self.admin_settings.items():
                    bot_logger.info(f"👤 Обрабатываем admin {admin_id}: {settings_data}")
                    
                    # Проверяем существует ли запись
                    result = await session.execute(
                        select(AdminDailyTasksSettings).where(
                            AdminDailyTasksSettings.telegram_user_id == admin_id
                        )
                    )
                    existing_settings = result.scalar_one_or_none()
                    
                    if existing_settings:
                        bot_logger.info(f"📝 Обновляем существующие настройки для admin {admin_id}")
                        # Обновляем существующую запись
                        for key, value in settings_data.items():
                            if hasattr(existing_settings, key):
                                # ⚡ Конвертируем строку времени в time объект
                                if key == 'notification_time' and isinstance(value, str):
                                    from datetime import time as time_obj
                                    try:
                                        hour, minute = map(int, value.split(':'))
                                        value = time_obj(hour, minute)
                                        bot_logger.info(f"🔧 Конвертировали {key}: '{value}' -> time объект")
                                    except Exception as e:
                                        bot_logger.error(f"❌ Ошибка конвертации времени {value}: {e}")
                                        continue

                                bot_logger.info(f"🔧 Устанавливаем {key} = {value} ({type(value)})")
                                setattr(existing_settings, key, value)
                            else:
                                bot_logger.warning(f"⚠️ Поле {key} не найдено в модели")
                    else:
                        bot_logger.info(f"🆕 Создаем новые настройки для admin {admin_id}")
                        new_settings = AdminDailyTasksSettings(
                            telegram_user_id=admin_id,
                            plane_email=settings_data.get('plane_email'),
                            enabled=settings_data.get('enabled', False),
                            notification_time=settings_data.get('notification_time'),
                            timezone=settings_data.get('timezone', 'Europe/Moscow'),
                            include_overdue=settings_data.get('include_overdue', True),
                            include_today=settings_data.get('include_today', True),
                            include_upcoming=settings_data.get('include_upcoming', True),
                            group_by_project=settings_data.get('group_by_project', True),
                            max_tasks_per_section=settings_data.get('max_tasks_per_section', 5)
                        )
                        session.add(new_settings)
                        bot_logger.info(f"➕ Добавили новую запись в сессию для admin {admin_id}")
                
                bot_logger.info("💾 Коммитим изменения в БД...")
                await session.commit()
                bot_logger.info("✅ Admin settings saved to database successfully")
                return True
                
        except Exception as e:
            bot_logger.error(f"❌ Error saving admin settings to database: {e}")
            bot_logger.error(f"📊 Current admin_settings: {self.admin_settings}")
            return False
    
    def _load_default_settings(self):
        """Загружает настройки по умолчанию (fallback)"""
        default_settings = {
            'enabled': settings.daily_tasks_enabled,
            'time': settings.daily_tasks_time,
            'timezone': settings.daily_tasks_timezone,
            'include_overdue': True,
            'include_today': True,
            'include_upcoming': True,
            'group_by_project': True,
            'max_tasks_per_section': 5
        }
        
        for admin_id in settings.admin_user_id_list:
            self.admin_settings[admin_id] = default_settings.copy()
        
        bot_logger.info(f"Loaded default settings for {len(self.admin_settings)} admins")
    
    async def get_admin_settings(self, admin_id: int) -> Dict[str, Any]:
        """Получить настройки админа"""
        if admin_id not in self.admin_settings:
            await self._load_admin_settings_from_db()
        return self.admin_settings.get(admin_id, {})
    
    async def update_admin_setting(self, admin_id: int, key: str, value: Any) -> bool:
        """Обновить настройку админа"""
        try:
            async with async_session() as session:
                # Получаем существующие настройки
                result = await session.execute(
                    select(AdminDailyTasksSettings).where(
                        AdminDailyTasksSettings.telegram_user_id == admin_id
                    )
                )
                admin_settings = result.scalar_one_or_none()
                
                if not admin_settings:
                    # Создаем новые настройки
                    await self._create_default_admin_settings(admin_id)
                    admin_settings = AdminDailyTasksSettings.from_dict(
                        self.admin_settings.get(admin_id, {}), 
                        admin_id
                    )
                    session.add(admin_settings)
                
                # Обновляем настройку  
                if key in ['time', 'notification_time']:
                    try:
                        hour, minute = map(int, value.split(':'))
                        admin_settings.notification_time = time(hour, minute)
                    except:
                        bot_logger.error(f"Invalid time format: {value}")
                        return False
                elif key == 'plane_email':
                    admin_settings.plane_email = value
                elif key == 'notifications_enabled':
                    admin_settings.enabled = value  # В БД поле называется 'enabled'
                elif hasattr(admin_settings, key):
                    setattr(admin_settings, key, value)
                else:
                    bot_logger.error(f"Unknown setting key: {key}")
                    return False
                
                await session.commit()
                
                # Обновляем кэш
                if admin_id not in self.admin_settings:
                    self.admin_settings[admin_id] = {}
                self.admin_settings[admin_id][key] = value
                
                bot_logger.info(f"Updated setting {key}={value} for admin {admin_id}")
                return True
                
        except Exception as e:
            bot_logger.error(f"Error updating admin setting: {e}")
            return False
    
    async def get_admin_tasks(self, admin_id: int) -> List[PlaneTask]:
        """Получить задачи админа из Plane"""
        try:
            admin_settings = self.admin_settings.get(admin_id, {})
            plane_email = admin_settings.get('plane_email')
            
            bot_logger.info(f"🔍 DEBUG: get_admin_tasks called for admin {admin_id}, email: {plane_email}")
            
            if not plane_email:
                bot_logger.warning(f"No plane_email configured for admin {admin_id}")
                return []
            
            # Получаем задачи по email из Plane
            bot_logger.info(f"🔍 DEBUG: Calling plane_api.get_user_tasks for email {plane_email}")
            tasks = await plane_api.get_user_tasks(plane_email)
            
            bot_logger.info(f"🔍 DEBUG: plane_api.get_user_tasks returned {len(tasks) if tasks else 0} tasks for admin {admin_id}")
            return tasks or []
            
        except Exception as e:
            bot_logger.error(f"Error getting tasks for admin {admin_id}: {e}")
            return []
    
    async def send_daily_tasks_to_admin(self, admin_id: int, force: bool = False) -> bool:
        """Отправить ежедневный список задач одному админу"""
        try:
            admin_settings = self.get_admin_settings(admin_id)
            
            if not admin_settings.get('enabled', False) and not force:
                bot_logger.debug(f"Daily tasks disabled for admin {admin_id}")
                return False
            
            # Получаем задачи админа из Plane
            tasks = await plane_api.get_all_assigned_tasks_by_user_id(admin_id)
            
            if not tasks and not force:
                bot_logger.info(f"No tasks found for admin {admin_id}")
                return True  # Это не ошибка
            
            # Формируем сообщение
            message = await self._format_daily_tasks_message(
                tasks, admin_settings, admin_id
            )
            
            # Отправляем сообщение
            await self.bot.send_message(
                chat_id=admin_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN_V2,
                disable_web_page_preview=True
            )
            
            # Логируем успешную отправку
            await self._log_daily_tasks_send(admin_id, True, tasks, plane_response_time)
            
            # Обновляем время последней отправки
            await self._update_last_sent_time(admin_id)
            
            bot_logger.info(f"Daily tasks sent to admin {admin_id}")
            return True
            
        except Exception as e:
            error_message = str(e)
            bot_logger.error(f"Error sending daily tasks to admin {admin_id}: {e}")
            
            # Логируем ошибку
            plane_response_time = int((datetime.now() - start_time).total_seconds() * 1000)
            await self._log_daily_tasks_send(admin_id, False, tasks, plane_response_time, error_message)
            
            return False
    
    async def send_daily_tasks_to_all_admins(self) -> Dict[int, bool]:
        """Отправить ежедневный список задач всем админам"""
        results = {}
        
        for admin_id in settings.admin_user_id_list:
            results[admin_id] = await self.send_daily_tasks_to_admin(admin_id)
        
        successful = sum(1 for success in results.values() if success)
        bot_logger.info(f"Daily tasks sent to {successful}/{len(results)} admins")
        
        return results
    
    async def _format_daily_tasks_message(
        self, 
        tasks: List[PlaneTask], 
        admin_settings: Dict[str, Any],
        admin_id: int
    ) -> str:
        """Форматирует сообщение с ежедневными задачами"""
        
        if not tasks:
            return (
                f"🌅 *Доброе утро\\!*\n\n"
                f"✨ У вас нет активных задач в Plane\\.\n"
                f"Отличное время для новых свершений\\! 🚀"
            )
        
        # Группируем задачи
        overdue_tasks = [t for t in tasks if t.is_overdue]
        today_tasks = [t for t in tasks if t.is_due_today and not t.is_overdue]
        upcoming_tasks = [t for t in tasks if not t.is_overdue and not t.is_due_today]
        
        message_parts = [f"🌅 *Доброе утро\\! Ваши задачи на сегодня:*\n"]
        
        # Просроченные задачи
        if overdue_tasks and admin_settings.get('include_overdue', True):
            message_parts.append("🔴 *ПРОСРОЧЕННЫЕ ЗАДАЧИ:*")
            for task in overdue_tasks[:5]:  # Максимум 5 задач
                message_parts.append(self._format_task_line(task))
            if len(overdue_tasks) > 5:
                message_parts.append(f"_\\.\\.\\. и ещё {len(overdue_tasks) - 5} просроченных_")
            message_parts.append("")
        
        # Задачи на сегодня
        if today_tasks and admin_settings.get('include_today', True):
            message_parts.append("📅 *НА СЕГОДНЯ:*")
            for task in today_tasks[:5]:
                message_parts.append(self._format_task_line(task))
            if len(today_tasks) > 5:
                message_parts.append(f"_\\.\\.\\. и ещё {len(today_tasks) - 5} на сегодня_")
            message_parts.append("")
        
        # Предстоящие задачи
        if upcoming_tasks and admin_settings.get('include_upcoming', True):
            message_parts.append("📋 *АКТИВНЫЕ ЗАДАЧИ:*")
            for task in upcoming_tasks[:8]:  # Максимум 8 задач
                message_parts.append(self._format_task_line(task))
            if len(upcoming_tasks) > 8:
                message_parts.append(f"_\\.\\.\\. и ещё {len(upcoming_tasks) - 8} активных_")
            message_parts.append("")
        
        # Статистика
        total_tasks = len(tasks)
        message_parts.extend([
            f"📊 *Всего активных задач:* {total_tasks}",
            f"🔴 Просрочено: {len(overdue_tasks)}",
            f"📅 На сегодня: {len(today_tasks)}",
            f"📋 В работе: {len(upcoming_tasks)}"
        ])
        
        # Ссылка на Plane
        if settings.plane_api_url:
            clean_url = settings.plane_api_url.replace('.', '\\.')
            message_parts.extend([
                "",
                f"🔗 [Открыть Plane]({clean_url})",
                "",
                "⚙️ Настроить уведомления: /daily\\_settings"
            ])
        
        return "\n".join(message_parts)
    
    def _format_task_line(self, task: PlaneTask) -> str:
        """Форматирует одну строку задачи"""
        # Ограничиваем длину названия
        name = task.name
        if len(name) > 40:
            name = name[:37] + "..."
        
        return (
            f"{task.priority_emoji} {task.state_emoji} "
            f"{escape_markdown(name)} "
            f"_{escape_markdown(task.project_name)}_"
        )
    
    def should_send_now(self, admin_id: int) -> bool:
        """Проверяет, нужно ли отправлять уведомления сейчас"""
        admin_settings = self.get_admin_settings(admin_id)
        
        if not admin_settings.get('enabled', False):
            return False
        
        try:
            # Получаем время отправки и часовой пояс админа
            send_time_str = admin_settings.get('time', '09:00')
            timezone_str = admin_settings.get('timezone', 'Europe/Moscow')
            
            # Парсим время
            hour, minute = map(int, send_time_str.split(':'))
            send_time = time(hour, minute)
            
            # Получаем текущее время в часовом поясе админа
            tz = pytz.timezone(timezone_str)
            now = datetime.now(tz)
            current_time = now.time()
            
            # Проверяем, что время совпадает (с точностью до минуты)
            return (
                current_time.hour == send_time.hour and
                current_time.minute == send_time.minute
            )
            
        except Exception as e:
            bot_logger.error(f"Error checking send time for admin {admin_id}: {e}")
            return False
    
    async def get_admin_stats(self, admin_id: int) -> Dict[str, Any]:
        """Получить статистику задач админа"""
        try:
            tasks = await plane_api.get_all_assigned_tasks_by_user_id(admin_id)
            
            overdue = [t for t in tasks if t.is_overdue]
            today = [t for t in tasks if t.is_due_today and not t.is_overdue]
            upcoming = [t for t in tasks if not t.is_overdue and not t.is_due_today]
            
            # Группировка по приоритетам
            by_priority = {}
            for task in tasks:
                priority = task.priority.lower()
                by_priority[priority] = by_priority.get(priority, 0) + 1
            
            # Группировка по проектам
            by_project = {}
            for task in tasks:
                project = task.project_name
                by_project[project] = by_project.get(project, 0) + 1
            
            return {
                'total': len(tasks),
                'overdue': len(overdue),
                'today': len(today),
                'upcoming': len(upcoming),
                'by_priority': by_priority,
                'by_project': by_project,
                'last_updated': datetime.now().isoformat()
            }
            
        except Exception as e:
            bot_logger.error(f"Error getting admin stats: {e}")
            return {'error': str(e)}


    async def _log_daily_tasks_send(
        self, 
        admin_id: int, 
        success: bool, 
        tasks: List[PlaneTask], 
        plane_response_time: int = None, 
        error_message: str = None
    ):
        """Логировать отправку ежедневных задач"""
        try:
            # Подсчитываем статистику задач
            overdue = [t for t in tasks if t.is_overdue]
            today = [t for t in tasks if t.is_due_today and not t.is_overdue]
            upcoming = [t for t in tasks if not t.is_overdue and not t.is_due_today]
            
            # Подготавливаем данные задач для анализа
            tasks_data = {
                'total': len(tasks),
                'by_priority': {},
                'by_project': {},
                'by_state': {}
            } if tasks else None
            
            if tasks:
                for task in tasks:
                    # Группировка по приоритетам
                    priority = task.priority.lower()
                    tasks_data['by_priority'][priority] = tasks_data['by_priority'].get(priority, 0) + 1
                    
                    # Группировка по проектам
                    project = task.project_name
                    tasks_data['by_project'][project] = tasks_data['by_project'].get(project, 0) + 1
                    
                    # Группировка по статусам
                    state = task.state_name.lower()
                    tasks_data['by_state'][state] = tasks_data['by_state'].get(state, 0) + 1
            
            async with async_session() as session:
                log_entry = DailyTasksLog(
                    telegram_user_id=admin_id,
                    success=success,
                    error_message=error_message,
                    total_tasks=len(tasks),
                    overdue_tasks=len(overdue),
                    today_tasks=len(today),
                    upcoming_tasks=len(upcoming),
                    plane_response_time=plane_response_time,
                    tasks_data=tasks_data
                )
                
                session.add(log_entry)
                await session.commit()
                
        except Exception as e:
            bot_logger.error(f"Error logging daily tasks send: {e}")
    
    async def _update_last_sent_time(self, admin_id: int):
        """Обновить время последней отправки"""
        try:
            async with async_session() as session:
                result = await session.execute(
                    select(AdminDailyTasksSettings).where(
                        AdminDailyTasksSettings.telegram_user_id == admin_id
                    )
                )
                admin_settings = result.scalar_one_or_none()
                
                if admin_settings:
                    admin_settings.last_sent_at = datetime.now()
                    await session.commit()
                    
        except Exception as e:
            bot_logger.error(f"Error updating last sent time: {e}")
    
    async def get_admin_email_mapping(self, admin_id: int) -> Optional[str]:
        """Получить email админа для Plane"""
        try:
            async with async_session() as session:
                result = await session.execute(
                    select(AdminDailyTasksSettings.plane_email).where(
                        AdminDailyTasksSettings.telegram_user_id == admin_id
                    )
                )
                email = result.scalar_one_or_none()
                return email
                
        except Exception as e:
            bot_logger.error(f"Error getting admin email mapping: {e}")
            return None
    
    async def set_admin_email_mapping(self, admin_id: int, email: str) -> bool:
        """Установить email админа для Plane"""
        try:
            return await self.update_admin_setting(admin_id, 'plane_email', email)
        except Exception as e:
            bot_logger.error(f"Error setting admin email mapping: {e}")
            return False

    async def set_admin_notification_time(self, admin_id: int, time_str: str) -> bool:
        """Установить время уведомлений админа"""
        try:
            return await self.update_admin_setting(admin_id, 'notification_time', time_str)
        except Exception as e:
            bot_logger.error(f"Error setting admin notification time: {e}")
            return False

    async def set_admin_notifications_enabled(self, admin_id: int, enabled: bool) -> bool:
        """Включить/выключить уведомления для админа"""
        try:
            return await self.update_admin_setting(admin_id, 'notifications_enabled', enabled)
        except Exception as e:
            bot_logger.error(f"Error setting admin notifications status: {e}")
            return False


# Функция инициализации сервиса
async def init_daily_tasks_service(bot: Bot):
    """Инициализировать сервис ежедневных задач"""
    global daily_tasks_service
    daily_tasks_service = DailyTasksService(bot)
    await daily_tasks_service._load_admin_settings_from_db()
    return daily_tasks_service


# Глобальный экземпляр сервиса (будет инициализирован в main.py)
daily_tasks_service: Optional[DailyTasksService] = None
