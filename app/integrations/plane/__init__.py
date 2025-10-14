"""
Plane API Integration - Modular Architecture

This module provides a clean interface to Plane.so API with:
- HTTP client abstraction
- Pydantic models for data validation
- Separate managers for tasks, projects, and users
- Comprehensive logging and error handling
- DIRECT PostgreSQL DATABASE ACCESS (bypasses rate-limited API)
"""
import aiohttp
from typing import List, Dict, Any, Optional

from ...utils.logger import bot_logger
from .client import PlaneAPIClient
from .models import PlaneTask, PlaneProject, PlaneUser, PlaneState
from .projects import PlaneProjectsManager
from .users import PlaneUsersManager
from .tasks import PlaneTasksManager
from .database import plane_db_client  # NEW: Direct DB access
from .exceptions import (
    PlaneAPIError,
    PlaneAuthError,
    PlaneNotFoundError,
    PlaneRateLimitError,
    PlaneValidationError
)


class PlaneAPI:
    """
    Main Plane API interface - backward compatible wrapper

    This class maintains the same interface as the original monolithic plane_api.py
    but delegates to modular components internally.
    """

    def __init__(self, api_url: str = None, api_token: str = None, workspace_slug: str = None):
        """Initialize Plane API with configuration"""
        self.api_url = api_url.rstrip('/') if api_url else None
        self.api_token = api_token
        self.workspace_slug = workspace_slug

        # Initialize modular components
        if self.configured:
            self._client = PlaneAPIClient(self.api_url, self.api_token, self.workspace_slug)
            self._projects_manager = PlaneProjectsManager(self._client)
            self._users_manager = PlaneUsersManager(self._client)
            self._tasks_manager = PlaneTasksManager(
                self._client,
                self._projects_manager,
                self._users_manager
            )
            bot_logger.info(f"✅ Plane API initialized: {self.api_url}, workspace: {self.workspace_slug}")
        else:
            self._client = None
            self._projects_manager = None
            self._users_manager = None
            self._tasks_manager = None
            bot_logger.warning("⚠️ Plane API not configured (missing credentials)")

    @property
    def configured(self) -> bool:
        """Check if API is properly configured"""
        return bool(self.api_url and self.api_token and self.workspace_slug)

    async def test_connection(self) -> Dict[str, Any]:
        """Test API connection and authentication"""
        if not self.configured:
            return {
                'success': False,
                'error': 'Plane API not configured'
            }

        try:
            async with aiohttp.ClientSession() as session:
                # Test by fetching workspace info
                endpoint = f"/api/v1/workspaces/{self.workspace_slug}/"
                await self._client.get(session, endpoint)

                return {
                    'success': True,
                    'message': 'Successfully connected to Plane API',
                    'workspace': self.workspace_slug
                }

        except PlaneAuthError as e:
            return {
                'success': False,
                'error': f'Authentication failed: {e}'
            }
        except PlaneAPIError as e:
            return {
                'success': False,
                'error': str(e)
            }
        except Exception as e:
            bot_logger.error(f"Connection test failed: {e}")
            return {
                'success': False,
                'error': f'Connection failed: {e}'
            }

    async def get_user_tasks(self, user_email: str) -> List[PlaneTask]:
        """
        Get all tasks assigned to user by email

        ⚡ OPTIMIZATION: Removed unnecessary states requests + sequential with delays
        This reduces 52+ API calls to 26 calls with proper rate limit handling.

        Args:
            user_email: Email address of the user

        Returns:
            List of PlaneTask objects sorted by priority

        Raises:
            ValueError: If email not found in workspace
            PlaneAPIError: If API request fails
        """
        if not self.configured:
            bot_logger.error("Plane API not configured")
            return []

        try:
            # ⚡ МАКСИМАЛЬНАЯ СКОРОСТЬ: коннектор с 50 одновременными соединениями
            connector = aiohttp.TCPConnector(
                limit=50,  # Максимум 50 одновременных запросов
                limit_per_host=50,  # К одному хосту (Plane API)
                ttl_dns_cache=300  # Кэш DNS на 5 минут
            )
            async with aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=60, connect=5)  # Быстрые таймауты
            ) as session:
                return await self._tasks_manager.get_user_tasks(session, user_email)

        except ValueError as e:
            # Re-raise email validation errors
            bot_logger.warning(f"⚠️ Email validation error: {e}")
            raise
        except Exception as e:
            bot_logger.error(f"Error getting user tasks: {e}")
            return []

    async def get_workspace_members(self) -> List[PlaneUser]:
        """Get all workspace members"""
        if not self.configured:
            return []

        try:
            async with aiohttp.ClientSession() as session:
                return await self._users_manager.get_workspace_members(session)
        except Exception as e:
            bot_logger.error(f"Error getting workspace members: {e}")
            return []

    async def get_all_projects(self) -> List[Dict[str, Any]]:
        """Get all projects in workspace (for backward compatibility)"""
        if not self.configured:
            return []

        try:
            async with aiohttp.ClientSession() as session:
                projects = await self._projects_manager.get_projects(session)
                # Convert to dict format for backward compatibility
                return [
                    {
                        'id': p.id,
                        'name': p.name,
                        'identifier': p.identifier,  # Add identifier (HARZL, HHIVP, etc.)
                        'description': p.description,
                        'workspace': p.workspace,
                        'created_at': p.created_at,
                        'updated_at': p.updated_at
                    }
                    for p in projects
                ]
        except Exception as e:
            bot_logger.error(f"Error getting all projects: {e}")
            return []

    async def find_user_by_email(self, user_email: str) -> Optional[PlaneUser]:
        """Find user by email address"""
        if not self.configured:
            return None

        try:
            async with aiohttp.ClientSession() as session:
                return await self._users_manager.find_user_by_email(session, user_email)
        except Exception as e:
            bot_logger.error(f"Error finding user by email: {e}")
            return None

    async def create_issue(
        self,
        project_id: str,
        name: str,
        description: str = "",
        priority: str = "medium",
        labels: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new issue in Plane

        Args:
            project_id: Plane project UUID
            name: Issue title
            description: Issue description
            priority: Priority level (urgent, high, medium, low, none)
            labels: List of label names

        Returns:
            Created issue data or None on failure
        """
        if not self.configured:
            bot_logger.error("Plane API not configured")
            return None

        try:
            async with aiohttp.ClientSession() as session:
                return await self._tasks_manager.create_issue(
                    session=session,
                    project_id=project_id,
                    name=name,
                    description=description,
                    priority=priority,
                    labels=labels,
                    assignees=assignees
                )
        except Exception as e:
            bot_logger.error(f"Error creating issue: {e}")
            return None

    async def get_issue_details(
        self,
        project_id: str,
        issue_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get full issue details including description

        Args:
            project_id: Plane project UUID
            issue_id: Plane issue UUID

        Returns:
            Full issue data or None on failure
        """
        if not self.configured:
            bot_logger.error("Plane API not configured")
            return None

        try:
            async with aiohttp.ClientSession() as session:
                return await self._tasks_manager.get_issue_details(
                    session=session,
                    project_id=project_id,
                    issue_id=issue_id
                )
        except Exception as e:
            bot_logger.error(f"Error getting issue details: {e}")
            return None

    async def get_issue_comments(
        self,
        project_id: str,
        issue_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get all comments for an issue

        Args:
            project_id: Plane project UUID
            issue_id: Plane issue UUID

        Returns:
            List of comment objects
        """
        if not self.configured:
            bot_logger.error("Plane API not configured")
            return []

        try:
            async with aiohttp.ClientSession() as session:
                return await self._tasks_manager.get_issue_comments(
                    session=session,
                    project_id=project_id,
                    issue_id=issue_id
                )
        except Exception as e:
            bot_logger.error(f"Error getting issue comments: {e}")
            return []

    async def create_issue_comment(
        self,
        project_id: str,
        issue_id: str,
        comment: str
    ) -> Optional[Dict[str, Any]]:
        """
        Create a comment on an issue

        Args:
            project_id: Plane project UUID
            issue_id: Plane issue UUID
            comment: Comment text

        Returns:
            Created comment object or None
        """
        if not self.configured:
            bot_logger.error("Plane API not configured")
            return None

        try:
            async with aiohttp.ClientSession() as session:
                return await self._tasks_manager.create_issue_comment(
                    session=session,
                    project_id=project_id,
                    issue_id=issue_id,
                    comment=comment
                )
        except Exception as e:
            bot_logger.error(f"Error creating comment: {e}")
            return None


# Create global instance using settings
from ...config import settings

plane_api = PlaneAPI(
    api_url=settings.plane_api_url,
    api_token=settings.plane_api_token,
    workspace_slug=settings.plane_workspace_slug
)


# Export all public classes and functions
__all__ = [
    'PlaneAPI',
    'plane_api',  # Global instance
    'PlaneTask',
    'PlaneProject',
    'PlaneUser',
    'PlaneState',
    'PlaneAPIError',
    'PlaneAuthError',
    'PlaneNotFoundError',
    'PlaneRateLimitError',
    'PlaneValidationError',
]
