"""
Plane API Users Module
"""
import aiohttp
from typing import List, Dict, Optional
from ...utils.logger import bot_logger
from .client import PlaneAPIClient
from .models import PlaneUser
from .exceptions import PlaneAPIError


class PlaneUsersManager:
    """Manage Plane workspace users"""

    def __init__(self, client: PlaneAPIClient):
        self.client = client

    async def get_workspace_members(self, session: aiohttp.ClientSession) -> List[PlaneUser]:
        """Get all workspace members from all accessible projects

        Note: Plane API v1 doesn't have a direct workspace-members endpoint that works.
        Instead, we collect members from all projects (some may return 403, which we ignore).
        """
        try:
            bot_logger.info(f"🔍 Fetching workspace members for '{self.client.workspace_slug}'")

            # First get all projects
            from .projects import PlaneProjectsManager
            projects_manager = PlaneProjectsManager(self.client)
            projects = await projects_manager.get_projects(session)

            if not projects:
                bot_logger.warning("⚠️ No projects found, cannot get workspace members")
                return []

            bot_logger.info(f"📋 Found {len(projects)} projects, fetching members from each...")

            # Collect unique members from all projects
            members_dict = {}  # user_id -> PlaneUser
            successful_projects = 0
            failed_projects = 0

            for project in projects:
                try:
                    # Get members for this project
                    endpoint = f"/api/v1/workspaces/{self.client.workspace_slug}/projects/{project.id}/members/"
                    data = await self.client.get(session, endpoint)

                    # Handle both list and dict responses
                    if isinstance(data, list):
                        members_data = data
                    elif isinstance(data, dict) and 'results' in data:
                        members_data = data.get('results', [])
                    else:
                        bot_logger.debug(f"⚠️ Project '{project.name[:30]}' unexpected format: {type(data)}")
                        continue

                    for member_data in members_data:
                        # Handle both formats: {member: {...}} and direct member object
                        if isinstance(member_data, dict):
                            if 'member' in member_data:
                                member_obj = member_data.get('member', {})
                            else:
                                # Direct member object
                                member_obj = member_data
                        else:
                            bot_logger.debug(f"⚠️ Unexpected member_data type: {type(member_data)}")
                            continue

                        if not member_obj:
                            continue

                        user_id = member_obj.get('id')
                        email = member_obj.get('email')

                        # DEBUG: Log first member to understand structure
                        if not members_dict and user_id and email:
                            member_keys = list(member_obj.keys())[:15] if isinstance(member_obj, dict) else []
                            bot_logger.info(f"🔍 FIRST MEMBER STRUCTURE: keys={member_keys}, id={user_id[:8] if user_id else None}..., email={email}")

                        # DEBUG: Log what we got
                        if not user_id or not email:
                            member_keys = list(member_obj.keys())[:10] if isinstance(member_obj, dict) else []
                            bot_logger.debug(f"⚠️ Member missing id/email. Keys: {member_keys}, id={user_id}, email={email}")
                            continue

                        if user_id and email and user_id not in members_dict:
                            try:
                                member = PlaneUser(
                                    id=user_id,
                                    email=email,
                                    first_name=member_obj.get('first_name', ''),
                                    last_name=member_obj.get('last_name', ''),
                                    display_name=member_obj.get('display_name'),
                                    avatar=member_obj.get('avatar'),
                                    is_active=member_obj.get('is_active', True)
                                )
                                members_dict[user_id] = member
                            except Exception as e:
                                bot_logger.warning(f"⚠️ Failed to parse member {email}: {e}")
                                continue

                    successful_projects += 1
                    bot_logger.debug(f"✅ Got {len(members_data)} members from '{project.name[:30]}' (total unique: {len(members_dict)})")

                except PlaneAPIError as e:
                    # 403 Forbidden is expected for projects user doesn't have access to
                    failed_projects += 1
                    bot_logger.debug(f"⏭️ Skipping project '{project.name[:30]}': {e}")
                    continue
                except Exception as e:
                    failed_projects += 1
                    bot_logger.debug(f"⏭️ Error getting members from '{project.name[:30]}': {e}")
                    continue

            members = list(members_dict.values())
            bot_logger.info(f"✅ Collected {len(members)} unique workspace members from {successful_projects}/{len(projects)} accessible projects")

            if failed_projects > 0:
                bot_logger.debug(f"📊 Skipped {failed_projects} projects (no access or errors)")

            return members

        except Exception as e:
            bot_logger.error(f"❌ Unexpected error fetching workspace members: {e}")
            raise PlaneAPIError(f"Failed to fetch workspace members: {e}")

    async def find_user_by_email(
        self,
        session: aiohttp.ClientSession,
        email: str
    ) -> Optional[PlaneUser]:
        """Find user by email address"""
        try:
            members = await self.get_workspace_members(session)
            email_lower = email.lower().strip()

            for member in members:
                if member.email.lower().strip() == email_lower:
                    bot_logger.info(f"✅ Found user: {member.email} (ID: {member.id[:8]}...)")
                    return member

            bot_logger.warning(f"⚠️ User not found with email: {email}")
            return None

        except Exception as e:
            bot_logger.error(f"❌ Error finding user by email: {e}")
            return None

    def create_user_id_to_email_map(self, members: List[PlaneUser]) -> Dict[str, str]:
        """Create mapping from user ID to email"""
        return {member.id: member.email for member in members}
