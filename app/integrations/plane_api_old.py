"""
Интеграция с Plane API для получения задач
"""
import aiohttp
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel

from ..utils.logger import bot_logger
from ..config import settings


class PlaneTask(BaseModel):
    """Модель задачи из Plane API"""
    id: str
    sequence_id: int
    name: str
    description: Optional[str] = None
    state_detail: Dict[str, Any]
    priority: str
    assignee_details: Optional[Dict[str, Any]] = None
    project_detail: Dict[str, Any]
    created_at: str
    updated_at: str
    target_date: Optional[str] = None
    
    @property
    def priority_emoji(self) -> str:
        """Эмодзи для приоритета"""
        priority_map = {
            'urgent': '🔴',
            'high': '🟠', 
            'medium': '🟡',
            'low': '🟢',
            'none': '⚪'
        }
        return priority_map.get(self.priority.lower(), '⚪')
    
    @property
    def state_emoji(self) -> str:
        """Эмодзи для состояния"""
        state_map = {
            'backlog': '📋',
            'todo': '📝',
            'in_progress': '⚡',
            'in progress': '⚡',
            'in_review': '👀',
            'in review': '👀',
            'done': '✅',
            'completed': '✅',
            'cancelled': '❌',
            'canceled': '❌'
        }
        state_name = self.state_detail.get('name', '').lower()
        return state_map.get(state_name, '📋')
    
    @property
    def assignee_name(self) -> str:
        """Имя исполнителя"""
        if not self.assignee_details:
            return "Не назначен"
        
        display_name = self.assignee_details.get('display_name')
        if display_name:
            return display_name
            
        first_name = self.assignee_details.get('first_name', '')
        last_name = self.assignee_details.get('last_name', '')
        return f"{first_name} {last_name}".strip() or "Неизвестно"
    
    @property
    def project_name(self) -> str:
        """Название проекта"""
        return self.project_detail.get('name', 'Неизвестный проект')
    
    @property
    def state_name(self) -> str:
        """Название состояния"""
        return self.state_detail.get('name', 'Неизвестно')
    
    @property
    def is_overdue(self) -> bool:
        """Проверяет, просрочена ли задача"""
        if not self.target_date:
            return False
        
        try:
            target = datetime.fromisoformat(self.target_date.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            return target < now and self.state_detail.get('name', '').lower() not in ['done', 'completed', 'cancelled', 'canceled']
        except:
            return False
    
    @property
    def is_due_today(self) -> bool:
        """Проверяет, назначена ли задача на сегодня"""
        if not self.target_date:
            return False
        
        try:
            target = datetime.fromisoformat(self.target_date.replace('Z', '+00:00'))
            today = datetime.now(timezone.utc).date()
            return target.date() == today
        except:
            return False


class PlaneAPIClient:
    """Клиент для работы с Plane API"""
    
    def __init__(self):
        self.api_url = settings.plane_api_url
        self.api_token = settings.plane_api_token
        self.workspace_slug = settings.plane_workspace_slug
        
        if not all([self.api_url, self.api_token, self.workspace_slug]):
            bot_logger.warning("Plane API not fully configured")
            self.configured = False
        else:
            self.configured = True
            bot_logger.info("Plane API client initialized")
    
    @property
    def headers(self) -> Dict[str, str]:
        """HTTP заголовки для API запросов"""
        return {
            'X-API-Key': self.api_token,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    async def get_user_tasks(self, user_email: str) -> List[PlaneTask]:
        """Получить все задачи пользователя"""
        if not self.configured:
            bot_logger.error("Plane API not configured")
            return []
        
        try:
            async with aiohttp.ClientSession() as session:
                # Сначала получаем ID пользователя по email
                user_id = await self._get_user_id_by_email(session, user_email)
                if not user_id:
                    bot_logger.warning(f"User not found: {user_email}")
                    return []
                
                # Получаем задачи пользователя (используем issues вместо my-issues)
                url = f"{self.api_url}/api/v1/workspaces/{self.workspace_slug}/issues/"
                
                async with session.get(url, headers=self.headers) as response:
                    if response.status != 200:
                        bot_logger.error(f"Failed to get tasks: {response.status} {await response.text()}")
                        return []
                    
                    data = await response.json()
                    tasks = []
                    
                    # Фильтруем задачи по исполнителю
                    for task_data in data:
                        if (task_data.get('assignee') == user_id and 
                            task_data.get('state_detail', {}).get('name', '').lower() not in ['done', 'completed', 'cancelled', 'canceled']):
                            tasks.append(PlaneTask(**task_data))
                    
                    bot_logger.info(f"Found {len(tasks)} active tasks for user {user_email}")
                    return tasks
                    
        except Exception as e:
            bot_logger.error(f"Error getting user tasks: {e}")
            return []
    
    async def _get_user_id_by_email(self, session: aiohttp.ClientSession, email: str) -> Optional[str]:
        """Получить ID пользователя по email"""
        try:
            url = f"{self.api_url}/api/v1/workspaces/{self.workspace_slug}/members/"
            
            async with session.get(url, headers=self.headers) as response:
                if response.status != 200:
                    return None
                
                members = await response.json()
                for member in members:
                    if member.get('member', {}).get('email') == email:
                        return member.get('member', {}).get('id')
                
                return None
                
        except Exception as e:
            bot_logger.error(f"Error getting user ID: {e}")
            return None
    
    async def get_all_assigned_tasks_by_user_id(self, user_id: int) -> List[PlaneTask]:
        """Получить все назначенные задачи по Telegram user_id"""
        if not self.configured:
            return []
        
        try:
            # В реальной ситуации тут нужно будет сопоставить telegram_user_id с email в Plane
            # Пока что возвращаем задачи для тестового пользователя
            # Это нужно будет настроить под вашу систему
            
            # Предполагаем, что у нас есть мапинг telegram_id -> email
            user_email = await self._get_user_email_by_telegram_id(user_id)
            if not user_email:
                return []
            
            return await self.get_user_tasks(user_email)
            
        except Exception as e:
            bot_logger.error(f"Error getting tasks for user {user_id}: {e}")
            return []
    
    async def _get_user_email_by_telegram_id(self, telegram_user_id: int) -> Optional[str]:
        """Получить email пользователя по Telegram ID"""
        try:
            # Импортируем здесь чтобы избежать циклических зависимостей
            from ..database.database import async_session
            from ..database.daily_tasks_models import AdminDailyTasksSettings
            from sqlalchemy import select
            
            async with async_session() as session:
                result = await session.execute(
                    select(AdminDailyTasksSettings.plane_email).where(
                        AdminDailyTasksSettings.telegram_user_id == telegram_user_id
                    )
                )
                email = result.scalar_one_or_none()
                
                if email:
                    bot_logger.info(f"Found email mapping for user {telegram_user_id}: {email}")
                    return email
                else:
                    bot_logger.warning(f"No email mapping found for user {telegram_user_id}")
                    return None
                    
        except Exception as e:
            bot_logger.error(f"Error getting user email mapping: {e}")
            return None

    async def test_connection(self) -> Dict[str, Any]:
        """Тестирование подключения к Plane API"""
        if not self.configured:
            return {
                'success': False,
                'error': 'Plane API не настроен. Проверьте переменные окружения.'
            }
        
        try:
            async with aiohttp.ClientSession() as session:
                # Тестируем получение проектов (рабочий endpoint)
                url = f"{self.api_url}/api/v1/workspaces/{self.workspace_slug}/projects/"
                
                bot_logger.info(f"Testing connection to: {url}")
                bot_logger.info(f"Using headers: {dict(self.headers)}")
                
                async with session.get(url, headers=self.headers) as response:
                    response_text = await response.text()
                    bot_logger.info(f"Response status: {response.status}")
                    bot_logger.info(f"Response text: {response_text[:200]}...")
                    
                    if response.status == 200:
                        data = await response.json()
                        return {
                            'success': True,
                            'workspace_name': data.get('name', 'Unknown'),
                            'workspace_id': data.get('id', 'Unknown')
                        }
                    else:
                        return {
                            'success': False,
                            'error': f'HTTP {response.status}: {response_text}'
                        }
                        
        except Exception as e:
            bot_logger.error(f"Connection test failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }


# Глобальный экземпляр клиента
plane_api = PlaneAPIClient()
