"""
Сервис для упоминаний и уведомлений исполнителей
"""
import json
from typing import List, Dict, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from aiogram import Bot

from ..database.work_journal_models import (
    WorkJournalEntry, 
    WorkJournalWorker, 
    UserNotificationPreferences
)
from ..database.models import BotUser
from ..utils.logger import bot_logger


class WorkerMentionService:
    """Сервис для упоминаний исполнителей и уведомлений"""
    
    def __init__(self, session: AsyncSession, bot: Bot):
        self.session = session
        self.bot = bot
    
    async def get_worker_mentions(self, worker_names: List[str]) -> List[Dict]:
        """Получить данные для упоминаний исполнителей"""
        result = await self.session.execute(
            select(WorkJournalWorker)
            .where(
                WorkJournalWorker.name.in_(worker_names),
                WorkJournalWorker.is_active == True,
                WorkJournalWorker.mention_enabled == True
            )
        )
        workers = result.scalars().all()
        
        mentions = []
        for worker in workers:
            mention_data = {
                "name": worker.name,
                "telegram_username": worker.telegram_username,
                "telegram_user_id": worker.telegram_user_id,
                "mention_text": f"@{worker.telegram_username}" if worker.telegram_username else worker.name
            }
            mentions.append(mention_data)
        
        return mentions
    
    def format_work_assignment_message(
        self, 
        entry: WorkJournalEntry, 
        creator_name: str,
        mentions: List[Dict]
    ) -> str:
        """Форматировать сообщение о назначении работы с упоминаниями"""
        
        # Формируем список упоминаний
        mention_texts = []
        for mention in mentions:
            mention_texts.append(mention["mention_text"])
        
        # Если нет упоминаний, показываем просто имена
        if not mention_texts:
            try:
                worker_names = json.loads(entry.worker_names)
                mention_texts = worker_names
            except (json.JSONDecodeError, TypeError):
                mention_texts = ["Исполнитель не указан"]
        
        workers_text = ", ".join(mention_texts)
        
        # Импортируем настройки для ссылки на Google Sheets
        from ..config import settings
        
        message = (
            f"📋 **Новая запись в журнале работ**\n\n"
            f"👥 **Исполнители:** {workers_text}\n"
            f"🏢 **Компания:** {entry.company}\n"
            f"📅 **Дата:** {entry.work_date.strftime('%d.%m.%Y')}\n"
            f"⏱ **Время:** {entry.work_duration}\n"
            f"🚗 **Тип:** {'Выезд' if entry.is_travel else 'Удаленно'}\n\n"
            f"📝 **Описание:**\n{entry.work_description}\n\n"
        )

        # Добавляем создателя и ссылку на Google Sheets (clickable link)
        message += f"👤 **Создал:** {creator_name}\n"

        if settings.google_sheets_url:
            # Markdown clickable link: [text](URL)
            message += f"[📊 Google Sheets]({settings.google_sheets_url})\n"

        message += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

        return message
    
    async def send_work_assignment_notifications(
        self, 
        entry: WorkJournalEntry, 
        creator_name: str,
        chat_id: int
    ) -> Tuple[bool, List[str]]:
        """
        Отправить уведомления о назначении работы
        
        Returns:
            Tuple[bool, List[str]]: (success, list_of_errors)
        """
        errors = []
        
        try:
            # Парсим исполнителей
            worker_names = json.loads(entry.worker_names)
            
            # Получаем данные для упоминаний
            mentions = await self.get_worker_mentions(worker_names)
            
            # Формируем сообщение с упоминаниями
            message = self.format_work_assignment_message(entry, creator_name, mentions)
            
            # Отправляем сообщение в чат с упоминаниями
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode="Markdown"
                )
                bot_logger.info(f"Work assignment notification sent to chat {chat_id}")
            except Exception as e:
                error_msg = f"Failed to send chat notification: {str(e)}"
                errors.append(error_msg)
                bot_logger.error(error_msg)
            
            # Отправляем персональные уведомления (если пользователь разрешил)
            for mention in mentions:
                if mention["telegram_user_id"]:
                    try:
                        # Проверяем настройки пользователя
                        user_prefs = await self.get_user_notification_preferences(
                            mention["telegram_user_id"]
                        )
                        
                        if user_prefs and user_prefs.enable_work_assignment_notifications:
                            personal_message = (
                                f"🔔 **Вам назначена работа**\n\n"
                                f"🏢 **Компания:** {entry.company}\n"
                                f"📅 **Дата:** {entry.work_date.strftime('%d.%m.%Y')}\n"
                                f"⏱ **Время:** {entry.work_duration}\n"
                                f"🚗 **Тип:** {'Выезд' if entry.is_travel else 'Удаленно'}\n\n"
                                f"📝 **Описание:**\n{entry.work_description}\n\n"
                                f"👤 **Назначил:** {creator_name}\n\n"
                                f"_Для отключения уведомлений используйте /settings_"
                            )
                            
                            await self.bot.send_message(
                                chat_id=mention["telegram_user_id"],
                                text=personal_message,
                                parse_mode="Markdown"
                            )
                            
                            bot_logger.info(f"Personal notification sent to {mention['name']} ({mention['telegram_user_id']})")
                        
                    except Exception as e:
                        error_msg = f"Failed to send personal notification to {mention['name']}: {str(e)}"
                        errors.append(error_msg)
                        bot_logger.warning(error_msg)
            
            return len(errors) == 0, errors
            
        except Exception as e:
            error_msg = f"Error in send_work_assignment_notifications: {str(e)}"
            errors.append(error_msg)
            bot_logger.error(error_msg)
            return False, errors
    
    async def get_user_notification_preferences(
        self, 
        telegram_user_id: int
    ) -> Optional[UserNotificationPreferences]:
        """Получить настройки уведомлений пользователя"""
        result = await self.session.execute(
            select(UserNotificationPreferences)
            .where(UserNotificationPreferences.telegram_user_id == telegram_user_id)
        )
        return result.scalar_one_or_none()
    
    async def set_user_notification_preferences(
        self,
        telegram_user_id: int,
        enable_work_assignments: bool = None,
        enable_mentions: bool = None
    ) -> UserNotificationPreferences:
        """Установить настройки уведомлений пользователя"""
        
        # Проверяем существующие настройки
        existing = await self.get_user_notification_preferences(telegram_user_id)
        
        if existing:
            # Обновляем существующие
            if enable_work_assignments is not None:
                existing.enable_work_assignment_notifications = enable_work_assignments
            if enable_mentions is not None:
                existing.enable_mentions_in_chat = enable_mentions
            
            await self.session.commit()
            return existing
        else:
            # Создаем новые настройки
            new_prefs = UserNotificationPreferences(
                telegram_user_id=telegram_user_id,
                enable_work_assignment_notifications=enable_work_assignments or False,
                enable_mentions_in_chat=enable_mentions or True
            )
            
            self.session.add(new_prefs)
            await self.session.commit()
            return new_prefs
    async def send_worker_private_notifications(
        self,
        entry: WorkJournalEntry,
        creator_name: str
    ) -> Tuple[bool, List[str]]:
        """
        Отправить уведомления исполнителям в личные сообщения
        
        Returns:
            Tuple[bool, List[str]]: (success, list_of_errors)
        """
        errors = []
        
        try:
            # Парсим исполнителей
            worker_names = json.loads(entry.worker_names)
            
            # Получаем всех работников с включенными уведомлениями
            stmt = select(WorkJournalWorker).where(
                WorkJournalWorker.name.in_(worker_names),
                WorkJournalWorker.mention_enabled == True
            )
            result = await self.session.execute(stmt)
            workers = result.scalars().all()
            
            success_count = 0
            
            for worker in workers:
                if not worker.telegram_username:
                    continue
                    
                try:
                    # Получаем Telegram ID пользователя по username
                    # Это упрощенная версия - в реальности нужна более сложная логика
                    # для поиска пользователей по username
                    
                    # Формируем персональное сообщение
                    message = (
                        f"🔔 **Вам назначена работа**\n\n"
                        f"🏢 **Компания:** {entry.company}\n"
                        f"📅 **Дата:** {entry.work_date.strftime('%d.%m.%Y')}\n"
                        f"⏱ **Время:** {entry.work_duration}\n"
                        f"🚗 **Тип:** {'Выезд' if entry.is_travel else 'Удаленно'}\n\n"
                        f"📝 **Описание:**\n{entry.work_description}\n\n"
                        f"👤 **Назначил:** {creator_name}"
                    )
                    
                    # Здесь должна быть логика отправки в личный чат
                    # Для простоты пока логируем
                    bot_logger.info(f"Would send private notification to {worker.name} (@{worker.telegram_username})")
                    success_count += 1
                    
                except Exception as e:
                    error_msg = f"Failed to send private notification to {worker.name}: {str(e)}"
                    errors.append(error_msg)
                    bot_logger.error(error_msg)
            
            if success_count > 0:
                bot_logger.info(f"Prepared {success_count} private notifications for workers")
                
            return len(errors) == 0, errors
            
        except Exception as e:
            error_msg = f"Error in send_worker_private_notifications: {str(e)}"
            errors.append(error_msg)
            bot_logger.error(error_msg)
            return False, errors
