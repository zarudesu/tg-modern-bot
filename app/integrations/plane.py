"""
Интеграция с Plane для получения уведомлений о задачах
"""
from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from aiogram import Bot
from aiogram.enums import ParseMode

from ..utils.logger import bot_logger
from ..utils.formatters import escape_markdown
from ..config import settings


class PlaneIssue(BaseModel):
    """Модель задачи Plane"""
    id: str
    name: str
    description: Optional[str] = None
    state: str
    priority: str
    assignee: Optional[str] = None
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


class PlaneNotificationService:
    """Сервис для обработки уведомлений от Plane"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        
        # Настройки чата и топика
        self.chat_id = getattr(settings, 'plane_chat_id', None)
        self.topic_id = getattr(settings, 'plane_topic_id', None)
        
        # Эмодзи для приоритетов
        self.priority_emoji = {
            'urgent': '🔴',
            'high': '🟠',
            'medium': '🟡',
            'low': '🟢',
            'none': '⚪'
        }
        
        # Эмодзи для статусов
        self.state_emoji = {
            'backlog': '📋',
            'todo': '📝',
            'in_progress': '⚡',
            'in_review': '👀',
            'done': '✅',
            'cancelled': '❌'
        }
    
    async def process_webhook(self, payload: PlaneWebhookPayload) -> bool:
        """Обработка webhook от Plane"""
        try:
            if not self.chat_id:
                bot_logger.warning("Plane chat_id not configured")
                return False
            
            # Определяем тип события
            if payload.event == "created":
                await self._send_issue_created(payload)
            elif payload.event == "updated":
                await self._send_issue_updated(payload)
            elif payload.event == "deleted":
                await self._send_issue_deleted(payload)
            else:
                bot_logger.info(f"Unknown Plane event: {payload.event}")
                return False
            
            return True
            
        except Exception as e:
            bot_logger.error(f"Error processing Plane webhook: {e}")
            return False
    
    async def _send_issue_created(self, payload: PlaneWebhookPayload):
        """Отправка уведомления о создании задачи"""
        issue = payload.issue
        actor = payload.actor
        
        priority_emoji = self.priority_emoji.get(issue.priority.lower(), '⚪')
        state_emoji = self.state_emoji.get(issue.state.lower(), '📋')
        
        message = (
            f"🆕 *Новая задача создана*\n\n"
            f"{priority_emoji} *Приоритет:* {escape_markdown(issue.priority.upper())}\n"
            f"{state_emoji} *Статус:* {escape_markdown(issue.state.title())}\n"
            f"📊 *Проект:* {escape_markdown(issue.project)}\n"
            f"👤 *Создал:* {escape_markdown(actor.get('display_name', 'Unknown'))}\n"
        )
        
        if issue.assignee:
            message += f"👨‍💻 *Исполнитель:* {escape_markdown(issue.assignee)}\n"
        
        message += f"\n📝 *{escape_markdown(issue.name)}*\n"
        
        if issue.description and len(issue.description.strip()) > 0:
            # Обрезаем описание если слишком длинное
            desc = issue.description.strip()
            if len(desc) > 200:
                desc = desc[:200] + "..."
            message += f"\n_{escape_markdown(desc)}_\n"
        
        message += f"\n🔗 [Открыть задачу](https://plane\\.hhivp\\.com/projects/{escape_markdown(issue.project)}/issues/{escape_markdown(issue.id)})"
        
        await self._send_to_topic(message)
    
    async def _send_issue_updated(self, payload: PlaneWebhookPayload):
        """Отправка уведомления об обновлении задачи"""
        issue = payload.issue
        actor = payload.actor
        changes = payload.changes or {}
        
        # Игнорируем незначительные изменения
        if not changes or all(key in ['updated_at', 'description'] for key in changes.keys()):
            return
        
        state_emoji = self.state_emoji.get(issue.state.lower(), '📋')
        
        message = (
            f"📝 *Задача обновлена*\n\n"
            f"📝 *{escape_markdown(issue.name)}*\n"
            f"👤 *Обновил:* {escape_markdown(actor.get('display_name', 'Unknown'))}\n\n"
        )
        
        # Добавляем информацию об изменениях
        if 'state' in changes:
            old_state = changes['state'].get('old', 'Unknown')
            new_state = changes['state'].get('new', issue.state)
            old_emoji = self.state_emoji.get(old_state.lower(), '📋')
            new_emoji = self.state_emoji.get(new_state.lower(), '📋')
            message += f"{old_emoji} {escape_markdown(old_state)} → {new_emoji} {escape_markdown(new_state)}\n"
        
        if 'priority' in changes:
            old_priority = changes['priority'].get('old', 'none')
            new_priority = changes['priority'].get('new', issue.priority)
            old_emoji = self.priority_emoji.get(old_priority.lower(), '⚪')
            new_emoji = self.priority_emoji.get(new_priority.lower(), '⚪')
            message += f"Приоритет: {old_emoji} {escape_markdown(old_priority)} → {new_emoji} {escape_markdown(new_priority)}\n"
        
        if 'assignee' in changes:
            old_assignee = changes['assignee'].get('old', 'Не назначен')
            new_assignee = changes['assignee'].get('new', issue.assignee or 'Не назначен')
            message += f"Исполнитель: {escape_markdown(old_assignee)} → {escape_markdown(new_assignee)}\n"
        
        message += f"\n🔗 [Открыть задачу](https://plane\\.hhivp\\.com/projects/{escape_markdown(issue.project)}/issues/{escape_markdown(issue.id)})"
        
        await self._send_to_topic(message)
    
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
