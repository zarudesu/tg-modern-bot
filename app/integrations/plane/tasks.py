"""
Plane API Tasks Module - Task retrieval and filtering logic
"""
import aiohttp
from typing import List, Dict, Optional
from ...utils.logger import bot_logger
from .client import PlaneAPIClient
from .models import PlaneTask, PlaneProject
from .projects import PlaneProjectsManager
from .users import PlaneUsersManager
from .exceptions import PlaneAPIError


class PlaneTasksManager:
    """Manage Plane tasks (issues)"""

    def __init__(
        self,
        client: PlaneAPIClient,
        projects_manager: PlaneProjectsManager,
        users_manager: PlaneUsersManager
    ):
        self.client = client
        self.projects_manager = projects_manager
        self.users_manager = users_manager
        self._projects_cache = []

    async def get_user_tasks(
        self,
        session: aiohttp.ClientSession,
        user_email: str
    ) -> List[PlaneTask]:
        """Get all tasks assigned to user by email"""
        try:
            # 1. Get all projects
            projects = await self.projects_manager.get_projects(session)
            if not projects:
                bot_logger.warning("No projects found")
                return []

            bot_logger.info(f"Processing {len(projects)} projects for assigned tasks of user {user_email}")

            # Cache projects for enrichment
            self._projects_cache = [
                {'id': p.id, 'name': p.name, 'description': p.description}
                for p in projects
            ]

            # 2. Get workspace members (once for all projects)
            bot_logger.info(f"🔍 Fetching workspace members")
            workspace_members = await self.users_manager.get_workspace_members(session)
            user_id_to_email = self.users_manager.create_user_id_to_email_map(workspace_members)

            bot_logger.info(f"📥 Retrieved {len(workspace_members)} workspace members")

            # Check if target email exists
            email_found = user_email in user_id_to_email.values()
            if email_found:
                bot_logger.info(f"✅ Found target user {user_email} in workspace")
            else:
                bot_logger.warning(f"❌ Email {user_email} not found in workspace")
                raise ValueError(f"Email {user_email} не найден в Plane. Проверьте правильность email адреса.")

            # 3. Get project states
            bot_logger.info(f"🔍 Fetching states for {len(projects)} projects")
            project_states = {}
            for project in projects:
                states = await self.projects_manager.get_project_states(session, project.id)
                if states:
                    project_states[project.id] = states

            bot_logger.info(f"Built user mapping with {len(user_id_to_email)} users")

            # 4. Get assigned tasks from each project
            bot_logger.info(f"🔄 Starting to fetch tasks from {len(projects)} projects for {user_email}")
            all_tasks = []

            for idx, project in enumerate(projects):
                bot_logger.info(f"🔍 [{idx+1}/{len(projects)}] Processing project: {project.name} (id={project.id[:8]})")

                project_states_for_project = project_states.get(project.id, {})
                project_tasks = await self._get_project_issues(
                    session=session,
                    project_id=project.id,
                    user_email=user_email,
                    user_id_to_email=user_id_to_email,
                    project_states=project_states_for_project,
                    assigned_only=True
                )

                if project_tasks:
                    bot_logger.info(f"  ✅ [{idx+1}/{len(projects)}] Found {len(project_tasks)} assigned tasks in '{project.name}'")
                    all_tasks.extend(project_tasks)
                    bot_logger.info(f"  📊 Total accumulated tasks: {len(all_tasks)}")
                else:
                    bot_logger.debug(f"  ⏭️ [{idx+1}/{len(projects)}] No assigned tasks in '{project.name}'")

            # Sort by priority
            bot_logger.info(f"🔄 Sorting {len(all_tasks)} tasks by priority")
            all_tasks = self._sort_tasks_by_priority(all_tasks)

            bot_logger.info(f"✅ FINAL RESULT: {len(all_tasks)} total tasks for user {user_email}")
            return all_tasks

        except ValueError as e:
            # Re-raise validation errors (email not found)
            raise
        except Exception as e:
            bot_logger.error(f"Error getting user tasks: {e}")
            raise PlaneAPIError(f"Failed to get user tasks: {e}")

    async def _get_project_issues(
        self,
        session: aiohttp.ClientSession,
        project_id: str,
        user_email: Optional[str] = None,
        user_id_to_email: Optional[Dict[str, str]] = None,
        project_states: Optional[Dict[str, Dict]] = None,
        assigned_only: bool = True
    ) -> List[PlaneTask]:
        """Get issues for a specific project with filtering"""
        try:
            bot_logger.info(f"🔍 [PROJECT {project_id[:8]}] Starting to fetch issues, user_email={user_email}, assigned_only={assigned_only}")

            # Use expand to get detailed assignee and state information
            endpoint = f"/api/v1/workspaces/{self.client.workspace_slug}/projects/{project_id}/issues/"
            params = {"expand": "assignees,state"}

            bot_logger.debug(f"🔍 [PROJECT {project_id[:8]}] API request: {endpoint}")
            data = await self.client.get(session, endpoint, params=params)

            if not data:
                bot_logger.warning(f"⚠️ [PROJECT {project_id[:8]}] API returned no data")
                return []

            # Extract issues from response
            issues = []
            if 'results' in data:
                issues = data['results']
            elif 'grouped_by' in data:
                for group in data['grouped_by'].values():
                    if isinstance(group, list):
                        issues.extend(group)
            elif isinstance(data, list):
                issues = data

            bot_logger.info(f"📋 [PROJECT {project_id[:8]}] API returned {len(issues)} total issues")

            # Filter tasks
            bot_logger.info(f"🔄 [PROJECT {project_id[:8]}] Starting to filter {len(issues)} issues")
            filtered_tasks = []
            skipped_done = 0
            skipped_no_assignee = 0
            skipped_wrong_assignee = 0

            for idx, issue in enumerate(issues):
                task_seq = issue.get('sequence_id', 'unknown')

                # Check if task is not completed
                state = issue.get('state', {})
                state_name = ''
                if isinstance(state, dict):
                    state_name = state.get('name', '').lower()
                elif issue.get('state_detail'):
                    state_name = issue.get('state_detail', {}).get('name', '').lower()

                bot_logger.debug(f"    🔍 [TASK {task_seq}] State check: state_name='{state_name}'")

                if state_name in ['done', 'completed', 'cancelled', 'canceled']:
                    bot_logger.debug(f"    ⏭️ [TASK {task_seq}] SKIP: State is '{state_name}'")
                    skipped_done += 1
                    continue

                assignee_details = issue.get('assignee_details')
                assignees = issue.get('assignees', [])

                bot_logger.debug(f"    🔍 [TASK {task_seq}] Assignee check: has_details={bool(assignee_details)}, assignees_count={len(assignees) if assignees else 0}")

                # Filter for assigned tasks only
                if assigned_only:
                    if not assignee_details and not assignees:
                        bot_logger.debug(f"    ⏭️ [TASK {task_seq}] SKIP: No assignees")
                        skipped_no_assignee += 1
                        continue

                    # Filter by email if specified
                    if user_email:
                        bot_logger.debug(f"    🔍 [TASK {task_seq}] Email matching for: {user_email}")
                        task_matched = False

                        # Check expanded assignees list
                        if assignees:
                            bot_logger.info(f"    📧 [TASK {task_seq}] Checking assignees: {[a.get('email') for a in assignees if isinstance(a, dict)]}")

                        # Match via expanded assignees (full objects)
                        if assignees and isinstance(assignees, list):
                            for assignee in assignees:
                                if isinstance(assignee, dict) and assignee.get('email') == user_email:
                                    bot_logger.info(f"✅ Found match via expanded assignee dict: {assignee}")
                                    bot_logger.info(f"🔍 Task {task_seq} state_name='{state_name}' (from state={state})")
                                    task_matched = True
                                    break

                        # Fallback: check via assignees (list of IDs) and mapping
                        if not task_matched and user_id_to_email:
                            bot_logger.debug(f"🔍 Checking assignee IDs against mapping")
                            for assignee_id in (assignees if isinstance(assignees, list) and all(isinstance(x, str) for x in assignees) else []):
                                email = user_id_to_email.get(assignee_id)
                                bot_logger.debug(f"🔍 Assignee ID {assignee_id[:8]}... -> email {email}")
                                if email == user_email:
                                    bot_logger.info(f"✅ Found match via user mapping: {assignee_id[:8]}... -> {email}")
                                    task_matched = True
                                    break

                        # Check via assignee_details (direct email)
                        if not task_matched and assignee_details:
                            if assignee_details.get('email') == user_email:
                                bot_logger.info(f"✅ Found match via assignee_details: {assignee_details}")
                                task_matched = True

                        bot_logger.info(f"🎯 Task {task_seq} final task_matched={task_matched}")

                        # Skip if task doesn't match email
                        if not task_matched:
                            skipped_wrong_assignee += 1
                            continue

                bot_logger.info(f"    ✅ [TASK {task_seq}] ADDING to filtered_tasks (passed all filters)")

                try:
                    # Enrich with project information
                    enriched_issue = issue.copy()

                    if self._projects_cache:
                        for project in self._projects_cache:
                            if project.get('id') == project_id:
                                enriched_issue['project_detail'] = project
                                enriched_issue['project_name'] = project.get('name', 'Unknown')
                                break

                    # Add state information
                    if project_states and issue.get('state'):
                        # Extract state_id from dict
                        state_id = issue['state'].get('id') if isinstance(issue['state'], dict) else issue['state']
                        state_info = project_states.get(state_id)
                        if state_info:
                            enriched_issue['state_detail'] = state_info
                            enriched_issue['state_name'] = state_info.get('name', 'Unknown')

                    bot_logger.debug(f"    🔧 [TASK {task_seq}] Creating PlaneTask object")
                    plane_task = PlaneTask(**enriched_issue)
                    filtered_tasks.append(plane_task)
                    bot_logger.info(f"    ✅ [TASK {task_seq}] Successfully added to filtered_tasks (total now: {len(filtered_tasks)})")

                except Exception as parse_error:
                    import traceback
                    bot_logger.error(f"Failed to parse issue {issue.get('id', 'unknown')}: {parse_error}")
                    bot_logger.error(f"Full traceback: {traceback.format_exc()}")
                    continue

            # Log filtering statistics
            bot_logger.info(f"📊 [PROJECT {project_id[:8]}] FILTERING COMPLETE:")
            bot_logger.info(f"  📥 Input: {len(issues)} total issues")
            bot_logger.info(f"  ✅ Output: {len(filtered_tasks)} filtered tasks")
            bot_logger.info(f"  ❌ Skipped (done): {skipped_done}")
            bot_logger.info(f"  ❌ Skipped (no assignee): {skipped_no_assignee}")
            bot_logger.info(f"  ❌ Skipped (wrong assignee): {skipped_wrong_assignee}")
            bot_logger.info(f"  📤 RETURNING {len(filtered_tasks)} tasks from project {project_id[:8]}")

            return filtered_tasks

        except PlaneAPIError as e:
            bot_logger.error(f"❌ API error getting project {project_id[:8]} issues: {e}")
            return []
        except Exception as e:
            bot_logger.error(f"❌ Error getting project {project_id[:8]} issues: {e}")
            return []

    def _sort_tasks_by_priority(self, tasks: List[PlaneTask]) -> List[PlaneTask]:
        """Sort tasks by priority and due date"""
        priority_order = {
            'urgent': 0,
            'high': 1,
            'medium': 2,
            'low': 3,
            'none': 4,
            None: 5
        }

        def sort_key(task: PlaneTask):
            priority_value = priority_order.get(task.priority, 5)
            # Tasks with due dates come first, then by priority
            has_due_date = 0 if task.target_date else 1
            return (has_due_date, priority_value, task.target_date or '')

        return sorted(tasks, key=sort_key)

    async def create_issue(
        self,
        session: aiohttp.ClientSession,
        project_id: str,
        name: str,
        description: str = "",
        priority: str = "medium",
        labels: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None
    ) -> Optional[Dict]:
        """
        Create a new issue in Plane

        Args:
            session: aiohttp client session
            project_id: Plane project UUID
            name: Issue title
            description: Issue description
            priority: Priority level (urgent, high, medium, low, none)
            labels: List of label UUIDs to attach
            assignees: List of user UUIDs to assign

        Returns:
            Created issue data or None on failure
        """
        try:
            endpoint = f"/api/v1/workspaces/{self.client.workspace_slug}/projects/{project_id}/issues/"

            # Prepare issue data
            issue_data = {
                "name": name,
                "description": description,
                "priority": priority,
            }

            # Add labels if provided
            if labels:
                issue_data["labels"] = labels

            # Add assignees if provided
            if assignees:
                issue_data["assignees"] = assignees

            bot_logger.info(f"📝 Creating issue in project {project_id[:8]}: {name[:50]}")

            # POST request to create issue
            response = await self.client.post(session, endpoint, json_data=issue_data)

            if response:
                issue_id = response.get('id', 'unknown')
                sequence_id = response.get('sequence_id', 'unknown')
                bot_logger.info(f"✅ Issue created successfully: #{sequence_id} (id={issue_id[:8]})")
                return response
            else:
                bot_logger.error("❌ Failed to create issue: No response from API")
                return None

        except PlaneAPIError as e:
            bot_logger.error(f"❌ Plane API error creating issue: {e}")
            return None
        except Exception as e:
            bot_logger.error(f"❌ Error creating issue: {e}")
            return None
