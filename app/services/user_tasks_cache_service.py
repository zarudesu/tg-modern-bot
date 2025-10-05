"""
Background service for caching user tasks from Plane.so API
"""

import asyncio
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import select, delete, update
from sqlalchemy.dialects.postgresql import insert

from ..database.database import get_async_session
from ..database.user_tasks_models import UserTasksCache, UserTasksSyncStatus
from ..integrations.plane import plane_api, PlaneTask
from ..utils.logger import bot_logger


class UserTasksCacheService:
    """Service for managing user tasks cache"""
    
    def __init__(self):
        self.bot_instance = None  # Will be set by main application
    
    async def start_user_sync(self, user_email: str, telegram_user_id: Optional[int] = None, notify_user: bool = True) -> bool:
        """
        Start background sync for user tasks
        Returns True if sync started, False if already in progress
        """
        try:
            # Check if sync is already in progress
            async for session in get_async_session():
                result = await session.execute(
                    select(UserTasksSyncStatus).where(
                        UserTasksSyncStatus.user_email == user_email
                    )
                )
                sync_status = result.scalar_one_or_none()
                
                if sync_status and sync_status.sync_in_progress:
                    bot_logger.info(f"Sync already in progress for {user_email}")
                    return False
                
                # Create or update sync status
                if not sync_status:
                    sync_status = UserTasksSyncStatus(
                        user_email=user_email,
                        telegram_user_id=telegram_user_id
                    )
                    session.add(sync_status)
                else:
                    sync_status.telegram_user_id = telegram_user_id
                
                sync_status.sync_in_progress = True
                sync_status.last_sync_started = datetime.now(timezone.utc)
                sync_status.last_sync_error = None
                
                await session.commit()
                bot_logger.info(f"🚀 Starting background sync for {user_email}")
                
                # Send notification to user
                if notify_user and telegram_user_id and self.bot_instance:
                    try:
                        await self.bot_instance.send_message(
                            telegram_user_id,
                            "⏳ <b>Загружаем ваши задачи из plane.hhivp.com...</b>\n\n"
                            "Это займет около 5 минут. Мы уведомим вас, когда загрузка завершится.\n\n"
                            "💡 <i>В следующий раз задачи будут отображаться мгновенно!</i>",
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        bot_logger.error(f"Failed to send notification to user {telegram_user_id}: {e}")
            
            # Start background task
            asyncio.create_task(self._sync_user_tasks_background(user_email, telegram_user_id))
            return True
            
        except Exception as e:
            bot_logger.error(f"Error starting sync for {user_email}: {e}")
            return False
    
    async def _sync_user_tasks_background(self, user_email: str, telegram_user_id: Optional[int] = None):
        """Background task to sync user tasks"""
        success = False
        error_message = None
        tasks_count = 0
        
        try:
            bot_logger.info(f"🔄 Background sync started for {user_email}")

            # Get tasks from Plane API
            tasks = await plane_api.get_user_tasks(user_email)
            bot_logger.info(f"📥 Retrieved {len(tasks)} tasks from Plane API for {user_email}")

            # Filter out completed tasks
            active_tasks = [
                task for task in tasks
                if task.get_state_name() not in ['done', 'completed', 'cancelled', 'canceled']
            ]

            bot_logger.info(f"📋 Filtered to {len(active_tasks)} active tasks for {user_email}")

            # Save to database
            tasks_count = await self._save_tasks_to_cache(user_email, active_tasks)

            success = True
            bot_logger.info(f"✅ Background sync completed for {user_email}: {tasks_count} tasks cached")

        except ValueError as e:
            # ⚠️ Email не найден в Plane - это не критичная ошибка, но нужно уведомить пользователя
            error_message = str(e)
            bot_logger.warning(f"⚠️ Email validation error for {user_email}: {e}")
        except Exception as e:
            error_message = str(e)
            bot_logger.error(f"❌ Background sync failed for {user_email}: {e}")
        
        finally:
            # Update sync status
            try:
                async for session in get_async_session():
                    result = await session.execute(
                        select(UserTasksSyncStatus).where(
                            UserTasksSyncStatus.user_email == user_email
                        )
                    )
                    sync_status = result.scalar_one_or_none()
                    
                    if sync_status:
                        sync_status.sync_in_progress = False
                        sync_status.total_tasks_found = tasks_count
                        
                        if success:
                            sync_status.last_sync_completed = datetime.now(timezone.utc)
                            sync_status.last_sync_error = None
                        else:
                            sync_status.last_sync_error = error_message
                        
                        await session.commit()
                
                # Send completion notification
                if telegram_user_id and self.bot_instance:
                    try:
                        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

                        if success:
                            message = (
                                f"✅ <b>Задачи загружены!</b>\n\n"
                                f"📊 Найдено активных задач: <b>{tasks_count}</b>\n\n"
                                f"Теперь вы можете мгновенно просматривать свои задачи через меню бота."
                            )
                            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="📋 Мои задачи", callback_data="daily_tasks")],
                                [InlineKeyboardButton(text="🏠 В главное меню", callback_data="start_menu")]
                            ])
                        else:
                            message = (
                                f"❌ <b>Ошибка загрузки задач</b>\n\n"
                                f"Произошла ошибка при загрузке ваших задач из plane.hhivp.com.\n\n"
                                f"Попробуйте еще раз позже или обратитесь к администратору."
                            )
                            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="refresh_tasks")],
                                [InlineKeyboardButton(text="🏠 В главное меню", callback_data="start_menu")]
                            ])

                        await self.bot_instance.send_message(
                            telegram_user_id,
                            message,
                            reply_markup=keyboard,
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        bot_logger.error(f"Failed to send completion notification to user {telegram_user_id}: {e}")
                        
            except Exception as e:
                bot_logger.error(f"Error updating sync status for {user_email}: {e}")
    
    async def _save_tasks_to_cache(self, user_email: str, tasks: List[PlaneTask]) -> int:
        """Save tasks to cache database, replacing existing ones"""
        try:
            async for session in get_async_session():
                # Delete existing tasks for user
                await session.execute(
                    delete(UserTasksCache).where(
                        UserTasksCache.user_email == user_email
                    )
                )
                
                # Insert new tasks
                if tasks:
                    cache_tasks = []
                    for task in tasks:
                        # Parse due date
                        due_date = None
                        if task.target_date:
                            try:
                                due_date = datetime.fromisoformat(task.target_date.replace('Z', '+00:00'))
                            except:
                                pass
                        
                        # Parse plane timestamps
                        plane_created_at = None
                        plane_updated_at = None
                        try:
                            if task.created_at:
                                plane_created_at = datetime.fromisoformat(task.created_at.replace('Z', '+00:00'))
                            if task.updated_at:
                                plane_updated_at = datetime.fromisoformat(task.updated_at.replace('Z', '+00:00'))
                        except:
                            pass
                        
                        # Extract state_id from Union[str, Dict] type
                        state_id = task.state
                        if isinstance(state_id, dict):
                            state_id = state_id.get('id', '')

                        # Extract project_id safely
                        project_id = ''
                        if task.project_detail:
                            if isinstance(task.project_detail, dict):
                                project_id = task.project_detail.get('id', '')
                            else:
                                project_id = getattr(task.project_detail, 'id', '')

                        # Extract assignee_email safely
                        assignee_email = ''
                        if task.assignee_details:
                            if isinstance(task.assignee_details, dict):
                                assignee_email = task.assignee_details.get('email', '')
                            else:
                                assignee_email = getattr(task.assignee_details, 'email', '')

                        cache_task = UserTasksCache(
                            user_email=user_email,
                            plane_task_id=task.id,
                            plane_project_id=project_id,
                            title=task.name,
                            description=task.description,
                            status=state_id.lower() if isinstance(state_id, str) else '',
                            priority=task.priority or 'none',
                            project_name=task.project_name,
                            assignee_name=task.assignee_name,
                            assignee_email=assignee_email,
                            state_name=task.state_name,
                            sequence_id=task.sequence_id,
                            due_date=due_date,
                            plane_created_at=plane_created_at,
                            plane_updated_at=plane_updated_at,
                            is_overdue=task.is_overdue,
                            is_due_today=task.is_due_today
                        )
                        cache_tasks.append(cache_task)
                    
                    session.add_all(cache_tasks)
                
                await session.commit()
                bot_logger.info(f"💾 Saved {len(tasks)} tasks to cache for {user_email}")
                return len(tasks)
                
        except Exception as e:
            bot_logger.error(f"Error saving tasks to cache for {user_email}: {e}")
            raise
    
    async def get_cached_tasks(
        self, 
        user_email: str,
        include_overdue: bool = True,
        include_today: bool = True,
        include_upcoming: bool = True,
        max_tasks: int = 50
    ) -> List[UserTasksCache]:
        """Get cached tasks for user with filtering"""
        try:
            async for session in get_async_session():
                query = select(UserTasksCache).where(
                    UserTasksCache.user_email == user_email
                )
                
                # Apply filters
                conditions = []
                if include_overdue:
                    conditions.append(UserTasksCache.is_overdue == True)
                if include_today:
                    conditions.append(UserTasksCache.is_due_today == True)
                if include_upcoming:
                    conditions.append(
                        (UserTasksCache.is_overdue == False) & 
                        (UserTasksCache.is_due_today == False)
                    )
                
                if conditions:
                    from sqlalchemy import or_
                    query = query.where(or_(*conditions))
                
                # Order by priority and due date
                # Priority order: urgent(0), high(1), medium(2), low(3), none(4)
                from sqlalchemy import case
                priority_order_case = case(
                    (UserTasksCache.priority == 'urgent', 0),
                    (UserTasksCache.priority == 'high', 1),
                    (UserTasksCache.priority == 'medium', 2),
                    (UserTasksCache.priority == 'low', 3),
                    else_=4  # 'none' or NULL
                )
                
                query = query.order_by(
                    UserTasksCache.is_overdue.desc(),
                    UserTasksCache.is_due_today.desc(),
                    priority_order_case,
                    UserTasksCache.due_date.nullslast(),
                    UserTasksCache.updated_at.desc()
                ).limit(max_tasks)
                
                result = await session.execute(query)
                tasks = result.scalars().all()
                
                bot_logger.debug(f"📄 Retrieved {len(tasks)} cached tasks for {user_email}")
                return list(tasks)
                
        except Exception as e:
            bot_logger.error(f"Error getting cached tasks for {user_email}: {e}")
            return []
    
    async def get_sync_status(self, user_email: str) -> Optional[UserTasksSyncStatus]:
        """Get sync status for user"""
        try:
            async for session in get_async_session():
                result = await session.execute(
                    select(UserTasksSyncStatus).where(
                        UserTasksSyncStatus.user_email == user_email
                    )
                )
                return result.scalar_one_or_none()
        except Exception as e:
            bot_logger.error(f"Error getting sync status for {user_email}: {e}")
            return None
    
    async def sync_all_users(self) -> int:
        """Sync tasks for all users who need updates (30+ minutes old)"""
        synced_count = 0
        try:
            async for session in get_async_session():
                # Get users who need sync
                now = datetime.now(timezone.utc)
                thirty_minutes_ago = datetime.fromtimestamp(now.timestamp() - 1800, timezone.utc)
                
                result = await session.execute(
                    select(UserTasksSyncStatus).where(
                        (UserTasksSyncStatus.sync_in_progress == False) &
                        (
                            (UserTasksSyncStatus.last_sync_completed == None) |
                            (UserTasksSyncStatus.last_sync_completed < thirty_minutes_ago)
                        )
                    )
                )
                
                users_to_sync = result.scalars().all()
                bot_logger.info(f"🔄 Found {len(users_to_sync)} users needing sync")
                
                for sync_status in users_to_sync:
                    success = await self.start_user_sync(
                        sync_status.user_email, 
                        sync_status.telegram_user_id,
                        notify_user=False  # Don't notify for automatic syncs
                    )
                    if success:
                        synced_count += 1
                        # Add delay between syncs to avoid overwhelming API
                        await asyncio.sleep(2)
                
        except Exception as e:
            bot_logger.error(f"Error in sync_all_users: {e}")
        
        if synced_count > 0:
            bot_logger.info(f"✅ Started sync for {synced_count} users")
        
        return synced_count


# Global service instance
user_tasks_cache_service = UserTasksCacheService()