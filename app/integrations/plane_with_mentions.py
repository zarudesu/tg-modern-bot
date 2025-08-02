"""
Расширенная интеграция с Plane с поддержкой упоминаний исполнителей
"""
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from pydantic import BaseModel, Field
from aiogram import Bot
from aiogram.enums import ParseMode
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..utils.logger import bot_logger
from ..utils.formatters import escape_markdown
from ..config import settings
from ..database.work_journal_models import WorkJournalWorker
from ..services.worker_mention_service import WorkerMentionService


class PlaneIssue(BaseModel):
    """Модель задачи Plane"""
    id: str
    name: str
    description: Optional[str] = None
    state: str
    priority: str
    assignee: Optional[str] = None  # Полное имя из Plane
    assignee_email: Optional[str] = None  # Email исполнителя
    project: str
    created_by: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class PlaneWebhookPayload(BaseModel):
    """Модель webhook payload от Plane"""
    event: str  # created, updated, deleted
    action: str
    issue: PlaneIssue
    changes: Optional[Dict[str, Any]] = None
    actor: Dict[str, str]  # Пользователь, выполнивший действие


class PlaneWorkerMapping:
    """Маппинг пользователей Plane на исполнителей в системе"""
    
    # Статичный маппинг имен Plane на имена исполнителей
    PLANE_TO_WORKER_MAPPING = {
        "Dmitriy Gusev": "Гусев Дима",
        "Dmitry Gusev": "Гусев Дима", 
        "Dima Gusev": "Гусев Дима",
        "Тимофей Батырев": "Тимофей Батырев",
        "Timofeij Batyrev": "Тимофей Батырев",
        "Konstantin Makeykin": "Константин Макейкин",
        "Kostya Makeykin": "Константин Макейкин",
    async def _get_assignee_mention(self, plane_assignee: str) -> Tuple[str, Optional[Dict]]:
        """
        Получить упоминание исполнителя и данные для ЛС уведомления
        
        Returns:
            Tuple[str, Optional[Dict]]: (отображаемое_имя, данные_для_упоминания)
        """
        if not plane_assignee:
            return "Не назначен", None
        
        # Получаем имя исполнителя из нашей системы через БД
        worker_mapping = PlaneWorkerMapping(self.session)
        worker_name = await worker_mapping.get_worker_name(plane_assignee)
        
        if not worker_name:
            # Если не нашли в маппинге, показываем оригинальное имя
            return escape_markdown(plane_assignee), None
        
        # Получаем данные для упоминания
        mentions = await self.mention_service.get_worker_mentions([worker_name])
        
        if mentions and len(mentions) > 0:
            mention_data = mentions[0]
            mention_text = mention_data["mention_text"]  # @username или имя
            return mention_text, mention_data
        else:
            # Если нет данных для упоминания, показываем имя из системы
            return escape_markdown(worker_name), None
    
    async def _send_issue_created(self, payload: PlaneWebhookPayload):
        """Отправка уведомления о создании задачи"""
        issue = payload.issue
        actor = payload.actor
        
        priority_emoji = self.priority_emoji.get(issue.priority.lower(), '⚪')
        state_emoji = self.state_emoji.get(issue.state.lower(), '📋')
        
        # Получаем упоминание исполнителя
        assignee_display, mention_data = await self._get_assignee_mention(issue.assignee)
        
        message = (
            f"╭─ 🎯 *{escape_markdown(issue.id)}*\n"
            f"├ 📝 {escape_markdown(issue.name)}\n"
            f"├ 📁 {escape_markdown(issue.project)}\n"
            f"├ {priority_emoji} {escape_markdown(issue.priority.title())} приоритет\n"
            f"├ 📅 {issue.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        )
        
        if issue.assignee:
            message += f"├ 👥 {assignee_display}\n"
        
        message += (
            f"├ {state_emoji} {escape_markdown(issue.state.title())}\n"
            f"╰─ 🔗 [Открыть в Plane](https://plane\\.hhivp\\.com/projects/{escape_markdown(issue.project)}/issues/{escape_markdown(issue.id)})"
        )
        
        # Отправляем в чат
        await self._send_to_topic(message)
        
        # Отправляем личное уведомление исполнителю (если есть)
        if mention_data and mention_data.get("telegram_user_id"):
            await self._send_personal_task_notification(issue, mention_data, "назначена")
    
    async def _send_issue_updated(self, payload: PlaneWebhookPayload):
        """Отправка уведомления об обновлении задачи"""
        issue = payload.issue
        actor = payload.actor
        changes = payload.changes or {}
        
        # Игнорируем незначительные изменения
        if not changes or all(key in ['updated_at', 'description'] for key in changes.keys()):
            return
        
        state_emoji = self.state_emoji.get(issue.state.lower(), '📋')
        priority_emoji = self.priority_emoji.get(issue.priority.lower(), '⚪')
        
        # Получаем упоминание исполнителя
        assignee_display, mention_data = await self._get_assignee_mention(issue.assignee)
        
        message = (
            f"📝 *Задача обновлена*\n\n"
            f"╭─ 🎯 *{escape_markdown(issue.id)}*\n"
            f"├ 📝 {escape_markdown(issue.name)}\n"
            f"├ 📁 {escape_markdown(issue.project)}\n"
        )
        
        # Показываем изменения
        changes_text = []
        
        if 'state' in changes:
            old_state = changes['state'].get('old', 'Unknown')
            new_state = changes['state'].get('new', issue.state)
            old_emoji = self.state_emoji.get(old_state.lower(), '📋')
            new_emoji = self.state_emoji.get(new_state.lower(), '📋')
            changes_text.append(f"├ 📊 {old_emoji} {escape_markdown(old_state)} → {new_emoji} {escape_markdown(new_state)}")
        
        if 'priority' in changes:
            old_priority = changes['priority'].get('old', 'none')
            new_priority = changes['priority'].get('new', issue.priority)
            old_emoji = self.priority_emoji.get(old_priority.lower(), '⚪')
            new_emoji = self.priority_emoji.get(new_priority.lower(), '⚪')
            changes_text.append(f"├ {old_emoji} {escape_markdown(old_priority)} → {new_emoji} {escape_markdown(new_priority)}")
        
        if 'assignee' in changes:
            old_assignee = changes['assignee'].get('old', 'Не назначен')
            old_assignee_display, _ = await self._get_assignee_mention(old_assignee)
            changes_text.append(f"├ 👥 {old_assignee_display} → {assignee_display}")
        else:
            if issue.assignee:
                changes_text.append(f"├ 👥 {assignee_display}")
        
        # Добавляем изменения в сообщение
        for change in changes_text:
            message += f"{change}\n"
        
        message += f"╰─ 🔗 [Открыть в Plane](https://plane\\.hhivp\\.com/projects/{escape_markdown(issue.project)}/issues/{escape_markdown(issue.id)})"
        
        # Отправляем в чат
        await self._send_to_topic(message)
        
        # Если изменился исполнитель, уведомляем нового
        if 'assignee' in changes and mention_data and mention_data.get("telegram_user_id"):
            await self._send_personal_task_notification(issue, mention_data, "переназначена")
    
    async def _send_issue_deleted(self, payload: PlaneWebhookPayload):
        """Отправка уведомления об удалении задачи"""
        issue = payload.issue
        actor = payload.actor
        
        message = (
            f"🗑️ *Задача удалена*\n\n"
            f"📝 *{escape_markdown(issue.name)}*\n"
            f"👤 *Удалил:* {escape_markdown(actor.get('display_name', 'Unknown'))}\n"
            f"📊 *Проект:* {escape_markdown(issue.project)}\n"
        )
        
        await self._send_to_topic(message)
    
    async def _send_personal_task_notification(
        self, 
        issue: PlaneIssue, 
        mention_data: Dict,
        action: str
    ):
        """Отправка личного уведомления исполнителю о задаче"""
        try:
            user_prefs = await self.mention_service.get_user_notification_preferences(
                mention_data["telegram_user_id"]
            )
            
            # Проверяем настройки пользователя
            if user_prefs and not user_prefs.enable_work_assignment_notifications:
                return
            
            priority_emoji = self.priority_emoji.get(issue.priority.lower(), '⚪')
            state_emoji = self.state_emoji.get(issue.state.lower(), '📝')
            
            personal_message = (
                f"🎯 **Вам {action} задача**\n\n"
                f"📝 **{issue.name}**\n\n"
                f"📁 **Проект:** {issue.project}\n"
                f"{priority_emoji} **Приоритет:** {issue.priority.title()}\n"
                f"{state_emoji} **Статус:** {issue.state.title()}\n"
                f"📅 **Дата:** {issue.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            )
            
            if issue.description and len(issue.description.strip()) > 0:
                desc = issue.description.strip()
                if len(desc) > 300:
                    desc = desc[:300] + "..."
                personal_message += f"📋 **Описание:**\n{desc}\n\n"
            
            personal_message += (
                f"🔗 [Открыть задачу](https://plane.hhivp.com/projects/{issue.project}/issues/{issue.id})\n\n"
                f"_Для отключения уведомлений используйте /settings_"
            )
            
            await self.bot.send_message(
                chat_id=mention_data["telegram_user_id"],
                text=personal_message,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
            
            bot_logger.info(f"Personal Plane notification sent to {mention_data['name']} ({mention_data['telegram_user_id']})")
            
        except Exception as e:
            bot_logger.warning(f"Failed to send personal Plane notification to {mention_data['name']}: {str(e)}")
    
    async def _send_to_topic(self, message: str):
        """Отправка сообщения в топик"""
        try:
            kwargs = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': ParseMode.MARKDOWN_V2,
                'disable_web_page_preview': True
            }
            
            # Если указан топик, добавляем его
            if self.topic_id:
                kwargs['message_thread_id'] = self.topic_id
            
            await self.bot.send_message(**kwargs)
            
            bot_logger.info(f"Plane notification sent to chat {self.chat_id}, topic {self.topic_id}")
            
        except Exception as e:
            bot_logger.error(f"Failed to send Plane notification: {e}")
            raise