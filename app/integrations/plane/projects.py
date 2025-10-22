"""
Plane API Projects Module
"""
import aiohttp
from typing import List, Dict
from ...utils.logger import bot_logger
from .client import PlaneAPIClient
from .models import PlaneProject, PlaneState
from .exceptions import PlaneAPIError


class PlaneProjectsManager:
    """Manage Plane projects"""

    def __init__(self, client: PlaneAPIClient):
        self.client = client

    async def get_projects(self, session: aiohttp.ClientSession) -> List[PlaneProject]:
        """Get all projects in workspace"""
        try:
            bot_logger.info(f"🔍 Fetching projects for workspace '{self.client.workspace_slug}'")

            endpoint = f"/api/v1/workspaces/{self.client.workspace_slug}/projects/"
            data = await self.client.get(session, endpoint)

            if not isinstance(data, dict) or 'results' not in data:
                bot_logger.error(f"❌ Unexpected API response format: {type(data)}")
                return []

            projects_data = data.get('results', [])
            bot_logger.info(f"📥 Retrieved {len(projects_data)} projects")

            projects = []
            for project_data in projects_data:
                try:
                    project = PlaneProject(
                        id=project_data.get('id', ''),
                        name=project_data.get('name', 'Unknown'),
                        identifier=project_data.get('identifier'),  # HARZL, HHIVP, etc.
                        description=project_data.get('description'),
                        workspace=project_data.get('workspace', ''),
                        created_at=project_data.get('created_at'),
                        updated_at=project_data.get('updated_at')
                    )
                    projects.append(project)
                except Exception as e:
                    bot_logger.warning(f"⚠️ Failed to parse project: {e}")
                    continue

            bot_logger.info(f"✅ Parsed {len(projects)} projects")
            return projects

        except PlaneAPIError as e:
            bot_logger.error(f"❌ API error fetching projects: {e}")
            raise
        except Exception as e:
            bot_logger.error(f"❌ Unexpected error fetching projects: {e}")
            raise PlaneAPIError(f"Failed to fetch projects: {e}")

    async def get_project_states(
        self,
        session: aiohttp.ClientSession,
        project_id: str
    ) -> Dict[str, Dict]:
        """Get all states for a project"""
        try:
            bot_logger.debug(f"🔍 Fetching states for project {project_id[:8]}...")

            endpoint = f"/api/v1/workspaces/{self.client.workspace_slug}/projects/{project_id}/states/"
            data = await self.client.get(session, endpoint)

            if not isinstance(data, dict) or 'results' not in data:
                bot_logger.warning(f"⚠️ Unexpected states response format for project {project_id[:8]}")
                return {}

            states_data = data.get('results', [])
            states_dict = {}

            for state in states_data:
                state_id = state.get('id')
                if state_id:
                    states_dict[state_id] = {
                        'id': state_id,
                        'name': state.get('name', 'Unknown'),
                        'color': state.get('color'),
                        'group': state.get('group')
                    }

            bot_logger.debug(f"✅ Retrieved {len(states_dict)} states for project {project_id[:8]}")
            return states_dict

        except PlaneAPIError as e:
            bot_logger.warning(f"⚠️ API error fetching states for project {project_id[:8]}: {e}")
            return {}
        except Exception as e:
            bot_logger.warning(f"⚠️ Error fetching states for project {project_id[:8]}: {e}")
            return {}

    async def get_all_project_states(
        self,
        session: aiohttp.ClientSession,
        projects: List[PlaneProject]
    ) -> Dict[str, Dict[str, Dict]]:
        """Get states for all projects"""
        bot_logger.info(f"🔄 Fetching states for {len(projects)} projects")

        all_states = {}
        for project in projects:
            project_states = await self.get_project_states(session, project.id)
            if project_states:
                all_states[project.id] = project_states

        bot_logger.info(f"✅ Retrieved states for {len(all_states)} projects")
        return all_states
