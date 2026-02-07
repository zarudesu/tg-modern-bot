"""
Plane API Tasks Module - Task retrieval and filtering logic
"""
import asyncio
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

    async def get_issue_details(
        self,
        session: aiohttp.ClientSession,
        project_id: str,
        issue_id: str
    ) -> Optional[Dict]:
        """
        Get full issue details including description and all metadata

        Args:
            session: aiohttp session
            project_id: Plane project UUID
            issue_id: Plane issue UUID

        Returns:
            Full issue data with description, assignees, labels, etc.
        """
        try:
            endpoint = f"/api/v1/workspaces/{self.client.workspace_slug}/projects/{project_id}/issues/{issue_id}/"
            params = {"expand": "assignees,state,labels"}

            bot_logger.info(f"📥 Fetching issue details: {issue_id}")
            data = await self.client.get(session, endpoint, params=params)

            if data:
                bot_logger.info(f"✅ Retrieved issue details for {issue_id}")
            return data

        except Exception as e:
            bot_logger.error(f"❌ Error fetching issue details: {e}")
            return None

    async def get_issue_comments(
        self,
        session: aiohttp.ClientSession,
        project_id: str,
        issue_id: str
    ) -> List[Dict]:
        """
        Get all comments for an issue

        Args:
            session: aiohttp session
            project_id: Plane project UUID
            issue_id: Plane issue UUID

        Returns:
            List of comment objects with actor, comment, created_at, etc.
        """
        try:
            endpoint = f"/api/v1/workspaces/{self.client.workspace_slug}/projects/{project_id}/issues/{issue_id}/comments/"

            bot_logger.info(f"💬 Fetching comments for issue: {issue_id}")
            data = await self.client.get(session, endpoint)

            comments = []
            if isinstance(data, list):
                comments = data
            elif isinstance(data, dict) and 'results' in data:
                comments = data['results']

            bot_logger.info(f"✅ Retrieved {len(comments)} comments for {issue_id}")

            # DEBUG: Log first comment structure to understand Plane API response
            if comments:
                bot_logger.debug(f"📋 First comment keys: {list(comments[0].keys())}")
                bot_logger.debug(f"📋 First comment FULL: {comments[0]}")

            return comments

        except Exception as e:
            bot_logger.error(f"❌ Error fetching issue comments: {e}")
            return []

    async def create_issue_comment(
        self,
        session: aiohttp.ClientSession,
        project_id: str,
        issue_id: str,
        comment: str
    ) -> Optional[Dict]:
        """
        Create a comment on an issue

        Args:
            session: aiohttp session
            project_id: Plane project UUID
            issue_id: Plane issue UUID
            comment: Comment text

        Returns:
            Created comment object or None
        """
        try:
            endpoint = f"/api/v1/workspaces/{self.client.workspace_slug}/projects/{project_id}/issues/{issue_id}/comments/"

            # Plane requires comment_html for rich text
            comment_html = f"<p>{comment}</p>" if comment else ""

            payload = {
                "comment_html": comment_html
            }

            bot_logger.info(f"💬 Creating comment on issue: {issue_id[:8]}...")
            data = await self.client.post(session, endpoint, json_data=payload)

            bot_logger.info(f"✅ Comment created: {data.get('id', 'N/A')[:8]}...")
            return data

        except Exception as e:
            bot_logger.error(f"❌ Error creating comment: {e}")
            return None

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

            bot_logger.info(f"Built user mapping with {len(user_id_to_email)} users")

            # 3. Get assigned tasks from all projects (NO states needed - comes in expand!)
            bot_logger.info(f"🔄 Fetching tasks from {len(projects)} projects for {user_email}")

            # PARALLEL processing - fetch all projects simultaneously for maximum speed
            bot_logger.info(f"⚡ Using parallel API requests for {len(projects)} projects")
            all_tasks = []

            # Create tasks for all projects at once
            fetch_tasks = []
            for project in projects:
                fetch_tasks.append(
                    self._get_project_issues(
                        session=session,
                        project_id=project.id,
                        user_email=user_email,
                        user_id_to_email=user_id_to_email,
                        project_states={},  # Not needed - state comes in expand
                        assigned_only=True
                    )
                )

            # Execute all requests in parallel
            results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

            # Process results
            for idx, (project, result) in enumerate(zip(projects, results), 1):
                if isinstance(result, Exception):
                    bot_logger.error(f"  ❌ Error in project '{project.name}': {result}")
                    continue

                if result:
                    bot_logger.info(f"  ✅ Found {len(result)} tasks in '{project.name}'")
                    all_tasks.extend(result)
                else:
                    bot_logger.debug(f"  ⏭️ No tasks in '{project.name}'")

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

                    # Add state information - use expanded state from API
                    state_obj = issue.get('state')
                    if isinstance(state_obj, dict):
                        # State expanded from API (via expand=state)
                        enriched_issue['state_detail'] = state_obj
                        enriched_issue['state_name'] = state_obj.get('name', 'Unknown')
                        bot_logger.debug(f"    🔧 [TASK {task_seq}] Enriched with state_name='{enriched_issue['state_name']}' from expanded API")
                    elif project_states and state_obj:
                        # Fallback: use project_states if provided
                        state_info = project_states.get(state_obj)
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
            # Plane requires description_html for rich text
            description_html = f"<p>{description}</p>" if description else ""

            issue_data = {
                "name": name,
                "description_html": description_html,
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

    async def search_open_issues(
        self,
        session: aiohttp.ClientSession,
        project_id: str,
        search_text: str,
        limit: int = 5
    ) -> List[Dict]:
        """
        Search for open issues by text match in name/description.

        Args:
            session: aiohttp session
            project_id: Plane project UUID
            search_text: Text to search for (case-insensitive substring)
            limit: Max results to return

        Returns:
            List of matching issues (id, sequence_id, name, state, assignees)
        """
        try:
            issues = await self._get_project_issues(
                session, project_id, assigned_only=False
            )

            if not issues:
                return []

            search_lower = search_text.lower()
            # Split search into keywords for better matching
            keywords = [w for w in search_lower.split() if len(w) > 2]

            scored = []
            for task in issues:
                name_lower = (task.name or "").lower()
                desc_lower = (task.description or "").lower()
                text = f"{name_lower} {desc_lower}"

                # Count keyword matches
                score = sum(1 for kw in keywords if kw in text)
                if score > 0:
                    scored.append((score, task))

            # Sort by score descending, take top N
            scored.sort(key=lambda x: x[0], reverse=True)

            results = []
            for score, task in scored[:limit]:
                results.append({
                    "id": task.id,
                    "sequence_id": task.sequence_id,
                    "name": task.name,
                    "state_name": task.state_name,
                    "assignee_names": task.assignee_names,
                    "priority": task.priority,
                    "updated_at": task.updated_at,
                    "score": score
                })

            return results

        except Exception as e:
            bot_logger.error(f"Error searching issues: {e}")
            return []

    async def get_all_issues_for_audit(
        self,
        session: aiohttp.ClientSession,
        project_id: str,
        include_done_since_days: int = 30
    ) -> List[PlaneTask]:
        """Get ALL issues for audit — including recently completed/cancelled.

        Unlike _get_project_issues, this doesn't skip done/cancelled tasks
        if they were updated within include_done_since_days.
        """
        try:
            endpoint = f"/api/v1/workspaces/{self.client.workspace_slug}/projects/{project_id}/issues/"
            params = {"expand": "assignees,state"}
            data = await self.client.get(session, endpoint, params=params)

            if not data:
                return []

            issues = []
            if 'results' in data:
                issues = data['results']
            elif 'grouped_by' in data:
                for group in data['grouped_by'].values():
                    if isinstance(group, list):
                        issues.extend(group)
            elif isinstance(data, list):
                issues = data

            from datetime import datetime, timedelta, timezone
            cutoff = datetime.now(timezone.utc) - timedelta(days=include_done_since_days)
            tasks = []

            for issue in issues:
                state = issue.get('state', {})
                state_name = ''
                if isinstance(state, dict):
                    state_name = state.get('name', '').lower()
                    issue['state_detail'] = state
                    issue['state_name'] = state.get('name', 'Unknown')

                # Skip old done/cancelled tasks
                if state_name in ('done', 'completed', 'cancelled', 'canceled'):
                    updated = issue.get('updated_at', '')
                    try:
                        dt = datetime.fromisoformat(updated.replace('Z', '+00:00'))
                        if dt < cutoff:
                            continue
                    except (ValueError, TypeError, AttributeError):
                        continue

                # Enrich assignee names
                assignees = issue.get('assignees', [])
                names = []
                for a in assignees:
                    if isinstance(a, dict):
                        names.append(a.get('display_name') or a.get('email', '?'))
                issue['assignee_name'] = ', '.join(names) if names else 'Unassigned'

                try:
                    tasks.append(PlaneTask(**issue))
                except Exception:
                    continue

            return tasks

        except Exception as e:
            bot_logger.error(f"Error in get_all_issues_for_audit: {e}")
            return []

    async def update_issue(
        self,
        session: aiohttp.ClientSession,
        project_id: str,
        issue_id: str,
        **fields
    ) -> Optional[Dict]:
        """Update issue fields via PATCH.

        Supported fields: state (UUID), priority, assignees (list of UUIDs),
        name, description_html.
        """
        try:
            endpoint = (
                f"/api/v1/workspaces/{self.client.workspace_slug}"
                f"/projects/{project_id}/issues/{issue_id}/"
            )
            return await self.client.patch(session, endpoint, json_data=fields)
        except Exception as e:
            bot_logger.error(f"Error updating issue {issue_id}: {e}")
            return None

    async def get_project_states(
        self,
        session: aiohttp.ClientSession,
        project_id: str
    ) -> List[Dict]:
        """Get all workflow states for a project.

        Returns list of dicts with id, name, group (backlog/unstarted/started/completed/cancelled).
        """
        try:
            endpoint = (
                f"/api/v1/workspaces/{self.client.workspace_slug}"
                f"/projects/{project_id}/states/"
            )
            data = await self.client.get(session, endpoint)
            if isinstance(data, dict):
                return data.get('results', [])
            return data if isinstance(data, list) else []
        except Exception as e:
            bot_logger.error(f"Error getting states for project {project_id}: {e}")
            return []
