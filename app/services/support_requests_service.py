"""
Support Requests Service

Управление заявками пользователей и интеграция с Plane API
"""

from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime, timezone

from ..database.support_requests_models import ChatPlaneMapping, SupportRequest
from ..integrations.plane import plane_api
from ..utils.logger import bot_logger
from ..config import settings


class SupportRequestsService:
    """Service for managing support requests"""

    async def get_chat_mapping(
        self,
        session: AsyncSession,
        chat_id: int
    ) -> Optional[ChatPlaneMapping]:
        """Get Plane project mapping for a chat"""
        result = await session.execute(
            select(ChatPlaneMapping).where(
                and_(
                    ChatPlaneMapping.chat_id == chat_id,
                    ChatPlaneMapping.is_active == True
                )
            )
        )
        return result.scalar_one_or_none()

    async def create_chat_mapping(
        self,
        session: AsyncSession,
        chat_id: int,
        chat_title: str,
        chat_type: str,
        plane_project_id: str,
        plane_project_name: str,
        created_by: int,
        allow_all_users: bool = True
    ) -> ChatPlaneMapping:
        """Create a new chat-to-project mapping"""
        mapping = ChatPlaneMapping(
            chat_id=chat_id,
            chat_title=chat_title,
            chat_type=chat_type,
            plane_project_id=plane_project_id,
            plane_project_name=plane_project_name,
            created_by=created_by,
            allow_all_users=allow_all_users,
            is_active=True
        )
        session.add(mapping)
        await session.commit()
        await session.refresh(mapping)

        bot_logger.info(
            f"Created chat mapping: {chat_id} ({chat_title}) -> "
            f"{plane_project_name} ({plane_project_id})"
        )
        return mapping

    async def update_chat_mapping(
        self,
        session: AsyncSession,
        chat_id: int,
        **updates
    ) -> Optional[ChatPlaneMapping]:
        """Update existing chat mapping"""
        mapping = await self.get_chat_mapping(session, chat_id)
        if not mapping:
            return None

        for key, value in updates.items():
            if hasattr(mapping, key):
                setattr(mapping, key, value)

        await session.commit()
        await session.refresh(mapping)
        return mapping

    async def delete_chat_mapping(
        self,
        session: AsyncSession,
        chat_id: int
    ) -> bool:
        """Deactivate chat mapping"""
        mapping = await self.get_chat_mapping(session, chat_id)
        if not mapping:
            return False

        mapping.is_active = False
        await session.commit()
        bot_logger.info(f"Deactivated chat mapping for chat {chat_id}")
        return True

    async def list_all_mappings(
        self,
        session: AsyncSession,
        only_active: bool = True
    ) -> List[ChatPlaneMapping]:
        """List all chat mappings"""
        query = select(ChatPlaneMapping)
        if only_active:
            query = query.where(ChatPlaneMapping.is_active == True)

        result = await session.execute(query.order_by(ChatPlaneMapping.created_at.desc()))
        return list(result.scalars().all())

    async def create_support_request(
        self,
        session: AsyncSession,
        chat_id: int,
        user_id: int,
        user_name: str,
        title: str,
        description: Optional[str] = None,
        priority: str = "medium"
    ) -> SupportRequest:
        """Create a new support request (not yet in Plane)"""
        # Get chat mapping first
        mapping = await self.get_chat_mapping(session, chat_id)
        if not mapping:
            raise ValueError(f"No active mapping found for chat {chat_id}")

        request = SupportRequest(
            chat_id=chat_id,
            user_id=user_id,
            user_name=user_name,
            title=title,
            description=description,
            priority=priority,
            plane_project_id=mapping.plane_project_id,
            status='pending'
        )
        session.add(request)
        await session.commit()
        await session.refresh(request)

        bot_logger.info(
            f"Created support request #{request.id} from user {user_id} "
            f"in chat {chat_id}: {title[:50]}"
        )
        return request

    async def submit_to_plane(
        self,
        session: AsyncSession,
        request_id: int
    ) -> Tuple[bool, Optional[str], Optional['SupportRequest']]:
        """
        Submit support request to Plane as an issue

        Returns:
            Tuple[bool, Optional[str], Optional[SupportRequest]]: (success, error_message, request_object)
        """
        # Get request
        result = await session.execute(
            select(SupportRequest).where(SupportRequest.id == request_id)
        )
        request = result.scalar_one_or_none()
        if not request:
            return False, "Request not found", None

        if request.status == 'created':
            return True, None, request  # Already created

        try:
            # Get all workspace members to assign all admins
            members = await plane_api.get_workspace_members()
            admin_member_ids = [member.id for member in members] if members else []

            # Create issue in Plane assigned to all admins
            issue_data = await plane_api.create_issue(
                project_id=request.plane_project_id,
                name=request.title,
                description=request.description or "",
                priority=request.priority,
                assignees=admin_member_ids  # Assign to all workspace members
                # labels removed - Plane requires UUIDs, not strings
            )

            if not issue_data:
                error_msg = "Failed to create issue in Plane (no response)"
                request.status = 'failed'
                request.error_message = error_msg
                await session.commit()
                return False, error_msg, None

            # Update request with Plane data
            request.plane_issue_id = issue_data.get('id')
            request.plane_sequence_id = issue_data.get('sequence_id')
            request.status = 'created'
            request.plane_created_at = datetime.now(timezone.utc)
            request.error_message = None

            await session.commit()
            await session.refresh(request)

            bot_logger.info(
                f"✅ Support request #{request.id} created in Plane: "
                f"{request.plane_project_id}/{request.plane_issue_id}"
            )
            return True, None, request

        except Exception as e:
            error_msg = str(e)
            request.status = 'failed'
            request.error_message = error_msg
            await session.commit()

            bot_logger.error(f"Failed to submit request #{request_id} to Plane: {e}")
            return False, error_msg, None

    async def get_user_requests(
        self,
        session: AsyncSession,
        user_id: int,
        limit: int = 10
    ) -> List[SupportRequest]:
        """Get user's recent support requests"""
        result = await session.execute(
            select(SupportRequest)
            .where(SupportRequest.user_id == user_id)
            .order_by(SupportRequest.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_request_by_id(
        self,
        session: AsyncSession,
        request_id: int
    ) -> Optional[SupportRequest]:
        """Get specific support request"""
        result = await session.execute(
            select(SupportRequest).where(SupportRequest.id == request_id)
        )
        return result.scalar_one_or_none()

    async def cancel_request(
        self,
        session: AsyncSession,
        request_id: int
    ) -> bool:
        """Cancel a pending request"""
        request = await self.get_request_by_id(session, request_id)
        if not request or request.status != 'pending':
            return False

        request.status = 'cancelled'
        await session.commit()
        bot_logger.info(f"Cancelled support request #{request_id}")
        return True

    async def get_pending_requests_count(
        self,
        session: AsyncSession,
        chat_id: Optional[int] = None
    ) -> int:
        """Get count of pending requests"""
        query = select(SupportRequest).where(SupportRequest.status == 'pending')
        if chat_id:
            query = query.where(SupportRequest.chat_id == chat_id)

        result = await session.execute(query)
        return len(list(result.scalars().all()))


# Global service instance
support_requests_service = SupportRequestsService()
