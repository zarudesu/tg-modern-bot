"""
Обработчик webhook для Plane уведомлений от n8n с системой упоминаний
"""
from typing import Dict, Any, Optional, Tuple
from pydantic import BaseModel
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from ..utils.logger import bot_logger
from ..services.worker_mention_service import WorkerMentionService
from ..database.work_journal_models import WorkJournalWorker
from ..database.database import get_async_session
from ..config import settings
from sqlalchemy import select


class PlaneWebhookData(BaseModel):
    """Модель данных от n8n для Plane задачи"""
    source: str = "plane_n8n"
    event_type: str  # plane_issue_created, plane_issue_updated, etc.
    data: Dict[str, Any]


class PlaneN8nHandler:
    """Обработчик Plane уведомлений от n8n с системой упоминаний"""
    
    def __init__(self, bot: Bot, session: AsyncSession):
        self.bot = bot
        self.session = session
        self.mention_service = WorkerMentionService(session, bot)
        
        # Настройки чата из конфигурации
        self.chat_id = getattr(settings, 'plane_chat_id', None)
        self.topic_id = getattr(settings, 'plane_topic_id', None)
        
        # Эмодзи
        self.priority_emoji = {
            'urgent': '🔴',
            'high': '🟠',
            'medium': '🟡', 
            'low': '🟢',
            'none': '⚪'
        }
        
        self.state_emoji = {
            'backlog': '📋',
            'todo': '📝',
            'in_progress': '⚡',
            'in_review': '👀',
            'done': '✅',
            'cancelled': '❌'
        }
    
    async def get_worker_mention_by_plane_name(self, plane_name: str) -> Tuple[str, Optional[Dict]]:
        """
        Получить упоминание по имени из Plane
        
        Returns:
            Tuple[str, Optional[Dict]]: (display_text, mention_data)
        """
        if not plane_name or plane_name.strip() == "":
            return "Не назначен", None
        
        # Ищем исполнителя по plane_user_names
        result = await self.session.execute(
            select(WorkJournalWorker)
            .where(
                WorkJournalWorker.is_active == True,
                WorkJournalWorker.plane_user_names.isnot(None)
            )
        )
        workers = result.scalars().all()
        
        plane_lower = plane_name.lower().strip()
        matched_worker = None
        
        for worker in workers:
            try:
                import json
                plane_names = json.loads(worker.plane_user_names)
                
                # Прямое соответствие
                if plane_name in plane_names:
                    matched_worker = worker
                    break
                
                # Частичное соответствие
                for name in plane_names:
                    if plane_lower in name.lower() or name.lower() in plane_lower:
                        matched_worker = worker
                        break
                        
                if matched_worker:
                    break
                    
            except (json.JSONDecodeError, TypeError):
                continue
        
        if not matched_worker:
            return f"_{plane_name}_", None  # Показываем курсивом если не нашли
        
        # Получаем данные для упоминания
        mentions = await self.mention_service.get_worker_mentions([matched_worker.name])
        
        if mentions and len(mentions) > 0:
            mention_data = mentions[0]
            return mention_data["mention_text"], mention_data
        else:
            return matched_worker.name, None
    
    async def process_plane_webhook(self, webhook_data: PlaneWebhookData) -> bool:
        """Обработать webhook от n8n с данными Plane"""
        try:
            if not self.chat_id:
                bot_logger.warning("Plane chat_id not configured")
                return False
            
            event_type = webhook_data.event_type
            data = webhook_data.data
            
            if event_type == "plane_issue_created":
                await self._handle_issue_created(data)
            elif event_type == "plane_issue_updated":
                await self._handle_issue_updated(data)
            elif event_type == "plane_issue_deleted":
                await self._handle_issue_deleted(data)
            else:
                bot_logger.info(f"Unknown Plane event type: {event_type}")
                return False
            
            return True
            
        except Exception as e:
            bot_logger.error(f"Error processing Plane webhook from n8n: {e}")
            return False
    
    async def _handle_issue_created(self, data: Dict[str, Any]):
        """Обработать создание задачи"""
        issue = data.get('issue', {})
        
        issue_id = issue.get('id', 'Unknown')
        title = issue.get('name', 'Без названия')
        project = issue.get('project', 'Unknown')
        priority = issue.get('priority', 'none').lower()
        state = issue.get('state', 'unknown').lower()
        assignee = issue.get('assignee')
        created_at = issue.get('created_at', '')
        
        # Получаем упоминание исполнителя
        assignee_display, mention_data = await self.get_worker_mention_by_plane_name(assignee)
        
        # Форматируем дату
        try:
            from datetime import datetime
            if created_at:
                dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                date_str = dt.strftime('%d.%m.%Y %H:%M')
            else:
                date_str = "Не указана"
        except:
            date_str = created_at or "Не указана"
        
        priority_emoji = self.priority_emoji.get(priority, '⚪')
        state_emoji = self.state_emoji.get(state, '📝')
        
        # Формируем сообщение в стиле как вы просили
        message = (
            f"╭─ 🎯 **{issue_id}**\n"
            f"├ 📝 {title}\n"
            f"├ 📁 {project}\n"
            f"├ {priority_emoji} {priority.title() if priority != 'none' else 'Без приоритета'}\n"
            f"├ 📅 {date_str}\n"
        )
        
        if assignee:
            message += f"├ 👥 {assignee_display}\n"
        
        message += (
            f"├ {state_emoji} {state.title()}\n"
            f"╰─ 🔗 Открыть в Plane"
        )
        
        # Отправляем в чат
        await self._send_to_chat(message)
        
        # Отправляем ЛС уведомление исполнителю
        if mention_data and mention_data.get("telegram_user_id"):
            await self._send_personal_notification(issue, mention_data, "назначена")
    
    async def _handle_issue_updated(self, data: Dict[str, Any]):
        """Обработать обновление задачи"""
        issue = data.get('issue', {})
        changes = data.get('changes', {})
        
        if not changes:
            return  # Нет значимых изменений
        
        issue_id = issue.get('id', 'Unknown')
        title = issue.get('name', 'Без названия')
        project = issue.get('project', 'Unknown')
        assignee = issue.get('assignee')
        
        # Получаем упоминание текущего исполнителя
        assignee_display, mention_data = await self.get_worker_mention_by_plane_name(assignee)
        
        message = (
            f"📝 **Задача обновлена**\n\n"
            f"╭─ 🎯 **{issue_id}**\n"
            f"├ 📝 {title}\n"
            f"├ 📁 {project}\n"
        )
        
        # Показываем изменения
        changes_shown = []
        
        if 'state' in changes:
            old_state = changes['state'].get('old', '')
            new_state = changes['state'].get('new', '')
            old_emoji = self.state_emoji.get(old_state.lower(), '📋')
            new_emoji = self.state_emoji.get(new_state.lower(), '📋')
            changes_shown.append(f"├ 📊 {old_emoji} {old_state} → {new_emoji} {new_state}")
        
        if 'priority' in changes:
            old_priority = changes['priority'].get('old', 'none')
            new_priority = changes['priority'].get('new', 'none')
            old_emoji = self.priority_emoji.get(old_priority.lower(), '⚪')
            new_emoji = self.priority_emoji.get(new_priority.lower(), '⚪')
            changes_shown.append(f"├ {old_emoji} {old_priority} → {new_emoji} {new_priority}")
        
        if 'assignee' in changes:
            old_assignee = changes['assignee'].get('old', 'Не назначен')
            old_display, _ = await self.get_worker_mention_by_plane_name(old_assignee)
            changes_shown.append(f"├ 👥 {old_display} → {assignee_display}")
        elif assignee:
            changes_shown.append(f"├ 👥 {assignee_display}")
        
        # Добавляем изменения
        for change in changes_shown:
            message += f"{change}\n"
        
        message += "╰─ 🔗 Открыть в Plane"
        
        # Отправляем в чат
        await self._send_to_chat(message)
        
        # Если назначили нового исполнителя, уведомляем его
        if 'assignee' in changes and mention_data and mention_data.get("telegram_user_id"):
            await self._send_personal_notification(issue, mention_data, "переназначена")
    
    async def _handle_issue_deleted(self, data: Dict[str, Any]):
        """Обработать удаление задачи"""
        issue = data.get('issue', {})
        
        issue_id = issue.get('id', 'Unknown')
        title = issue.get('name', 'Без названия')
        project = issue.get('project', 'Unknown')
        
        message = (
            f"🗑️ **Задача удалена**\n\n"
            f"📝 **{title}**\n"
            f"🎯 **ID:** {issue_id}\n"
            f"📁 **Проект:** {project}"
        )
        
        await self._send_to_chat(message)
    
    async def _send_personal_notification(self, issue: Dict, mention_data: Dict, action: str):
        """Отправить личное уведомление исполнителю"""
        try:
            # Проверяем настройки пользователя
            user_prefs = await self.mention_service.get_user_notification_preferences(
                mention_data["telegram_user_id"]
            )
            
            if user_prefs and not user_prefs.enable_work_assignment_notifications:
                return
            
            title = issue.get('name', 'Без названия')
            project = issue.get('project', 'Unknown')
            priority = issue.get('priority', 'none')
            state = issue.get('state', 'unknown')
            description = issue.get('description', '')
            
            personal_message = (
                f"🎯 **Вам {action} задача**\n\n"
                f"📝 **{title}**\n\n"
                f"📁 **Проект:** {project}\n"
                f"⚪ **Приоритет:** {priority.title()}\n"
                f"📊 **Статус:** {state.title()}\n\n"
            )
            
            if description and len(description.strip()) > 0:
                desc = description.strip()
                if len(desc) > 300:
                    desc = desc[:300] + "..."
                personal_message += f"📋 **Описание:**\n{desc}\n\n"
            
            personal_message += (
                f"🔗 [Открыть задачу](https://plane.hhivp.com/)\n\n"
                f"_Для отключения уведомлений используйте /settings_"
            )
            
            await self.bot.send_message(
                chat_id=mention_data["telegram_user_id"],
                text=personal_message,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
            
            bot_logger.info(f"Personal Plane notification sent to {mention_data['name']}")
            
        except Exception as e:
            bot_logger.warning(f"Failed to send personal Plane notification: {str(e)}")
    
    async def _send_to_chat(self, message: str):
        """Отправить сообщение в чат"""
        try:
            kwargs = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': "Markdown",
                'disable_web_page_preview': True
            }
            
            if self.topic_id:
                kwargs['message_thread_id'] = self.topic_id
            
            await self.bot.send_message(**kwargs)
            
            bot_logger.info(f"Plane notification sent to chat {self.chat_id}")
            
        except Exception as e:
            bot_logger.error(f"Failed to send Plane notification to chat: {e}")
            raise
