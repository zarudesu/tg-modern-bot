"""
Task Reports Service - Business logic for client task reports

When a task is completed in Plane, this service:
1. Creates TaskReport from webhook data
2. Maps Plane user to Telegram admin
3. Fetches comments and description from Plane API
4. Auto-generates report from comments + description
5. Manages report status transitions
6. Sends reports to clients
"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
import json

from ..database.task_reports_models import TaskReport
from ..database.support_requests_models import SupportRequest
from ..database.work_journal_models import WorkJournalEntry
from ..utils.logger import bot_logger
from ..config import settings


class TaskReportsService:
    """Service for managing task reports lifecycle"""

    # ═══════════════════════════════════════════════════════════
    # PLANE USER → TELEGRAM ADMIN MAPPING
    # ═══════════════════════════════════════════════════════════

    # Static mapping: Plane display_name/email → Telegram data
    PLANE_TO_TELEGRAM_MAP = {
        # Zardes / Костя Макейкин / Константин Макейкин
        "Zardes": {
            "telegram_username": "zardes",
            "telegram_id": 28795547
        },
        "Костя": {
            "telegram_username": "zardes",
            "telegram_id": 28795547
        },
        "Константин Макейкин": {
            "telegram_username": "zardes",
            "telegram_id": 28795547
        },
        "Костя Макейкин": {
            "telegram_username": "zardes",
            "telegram_id": 28795547
        },
        "zarudesu@gmail.com": {
            "telegram_username": "zardes",
            "telegram_id": 28795547
        },

        # Дима Гусев
        "Дима Гусев": {
            "telegram_username": "dima_gusev",
            "telegram_id": 132228544
        },
        "Дима": {
            "telegram_username": "dima_gusev",
            "telegram_id": 132228544
        },
        "gen.director@hhivp.com": {
            "telegram_username": "dima_gusev",
            "telegram_id": 132228544
        },

        # Тимофей Батырев
        "Тимофей Батырев": {
            "telegram_username": "timofey_batyrev",
            "telegram_id": 56994156
        },
        "Тимофей": {
            "telegram_username": "timofey_batyrev",
            "telegram_id": 56994156
        },
        "tim.4ud@gmail.com": {
            "telegram_username": "timofey_batyrev",
            "telegram_id": 56994156
        },
    }

    def map_plane_user_to_telegram(
        self,
        plane_name: Optional[str] = None,
        plane_email: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Map Plane user to Telegram data

        Args:
            plane_name: display_name or first_name from Plane
            plane_email: Email from Plane actor

        Returns:
            Dict with telegram_username and telegram_id (or None if not found)
        """
        # Try by name first
        if plane_name and plane_name in self.PLANE_TO_TELEGRAM_MAP:
            return self.PLANE_TO_TELEGRAM_MAP[plane_name]

        # Try by email
        if plane_email and plane_email in self.PLANE_TO_TELEGRAM_MAP:
            return self.PLANE_TO_TELEGRAM_MAP[plane_email]

        # Not found
        bot_logger.warning(
            f"⚠️ No Telegram mapping for Plane user: name={plane_name}, email={plane_email}"
        )
        return {
            "telegram_username": None,
            "telegram_id": None
        }

    # ═══════════════════════════════════════════════════════════
    # CREATE TASK REPORT FROM WEBHOOK
    # ═══════════════════════════════════════════════════════════

    async def create_task_report_from_webhook(
        self,
        session: AsyncSession,
        webhook_data: Dict[str, Any]
    ) -> Optional[TaskReport]:
        """
        Create TaskReport from n8n webhook when task is Done

        Expected webhook_data structure:
        {
            "plane_issue_id": "uuid",
            "plane_sequence_id": 123,  # HHIVP-123
            "plane_project_id": "uuid",
            "task_title": "Task name",
            "task_description": "Full description...",
            "closed_by": {
                "display_name": "Zardes",
                "first_name": "Zardes",
                "email": "zarudesu@gmail.com"
            },
            "closed_at": "2025-10-07T12:00:00Z",
            "support_request_id": 5  # Extracted from description (optional)
        }

        Returns:
            Created TaskReport or None on failure
        """
        try:
            plane_issue_id = webhook_data.get("plane_issue_id")
            if not plane_issue_id:
                bot_logger.error("❌ Missing plane_issue_id in webhook data")
                return None

            # Check if already exists
            existing = await self.get_task_report_by_plane_issue(session, plane_issue_id)
            if existing:
                # If task was already completed, this is a duplicate (task moved Done→ToDo→Done)
                if existing.status == "completed":
                    bot_logger.warning(
                        f"🔄 Duplicate webhook: TaskReport #{existing.id} for plane_issue={plane_issue_id} "
                        f"already completed. Ignoring to prevent re-reporting."
                    )
                    return None  # Return None to prevent duplicate admin notification

                # If status is pending/cancelled, allow recreation (legitimate re-completion)
                bot_logger.info(
                    f"♻️ Re-creating TaskReport for plane_issue={plane_issue_id} "
                    f"(previous status: {existing.status})"
                )
                # Delete old incomplete report to start fresh
                await session.delete(existing)
                await session.flush()

            # Map Plane user → Telegram
            closed_by = webhook_data.get("closed_by", {})
            plane_name = closed_by.get("display_name") or closed_by.get("first_name")
            plane_email = closed_by.get("email")

            telegram_mapping = self.map_plane_user_to_telegram(plane_name, plane_email)

            # Get support request if available
            support_request_id = webhook_data.get("support_request_id")
            support_request = None
            if support_request_id:
                support_request = await self.get_support_request(session, support_request_id)

            # Get client info from support request
            client_chat_id = None
            client_user_id = None
            client_message_id = None
            if support_request:
                client_chat_id = support_request.chat_id
                client_user_id = support_request.user_id
                # Note: client_message_id might be stored in support_request if available

            # Create TaskReport
            task_report = TaskReport(
                # Support Request link
                support_request_id=support_request_id,

                # Plane task info
                plane_issue_id=plane_issue_id,
                plane_sequence_id=webhook_data.get("plane_sequence_id"),
                plane_project_id=webhook_data.get("plane_project_id"),
                task_title=webhook_data.get("task_title"),
                task_description=webhook_data.get("task_description"),

                # Who closed
                closed_by_plane_name=plane_name,
                closed_by_telegram_username=telegram_mapping.get("telegram_username"),
                closed_by_telegram_id=telegram_mapping.get("telegram_id"),
                closed_at=self._parse_datetime(webhook_data.get("closed_at")),

                # Client info
                client_chat_id=client_chat_id,
                client_user_id=client_user_id,
                client_message_id=client_message_id,

                # Status
                status="pending",

                # Metadata
                webhook_payload=str(webhook_data),
            )

            session.add(task_report)
            await session.commit()
            await session.refresh(task_report)

            bot_logger.info(
                f"✅ Created TaskReport #{task_report.id} for "
                f"Plane issue {task_report.plane_sequence_id}"
            )

            # Fetch comments and description from Plane API AND auto-fill metadata
            await self.fetch_and_generate_report_from_plane(session, task_report)

            # Try to autofill from work_journal (as fallback if Plane data is empty)
            if not task_report.report_text:
                await self.try_autofill_from_work_journal(session, task_report)

            return task_report

        except Exception as e:
            bot_logger.error(f"❌ Error creating TaskReport from webhook: {e}")
            await session.rollback()
            return None

    # ═══════════════════════════════════════════════════════════
    # FETCH FROM PLANE API AND AUTO-GENERATE REPORT
    # ═══════════════════════════════════════════════════════════

    async def fetch_and_generate_report_from_plane(
        self,
        session: AsyncSession,
        task_report: TaskReport
    ) -> bool:
        """
        Fetch comments and description from Plane API and auto-generate report

        Args:
            session: Database session
            task_report: TaskReport to populate

        Returns:
            True if report was generated, False otherwise
        """
        try:
            from ..integrations.plane import plane_api

            if not plane_api.configured:
                bot_logger.warning("⚠️ Plane API not configured, skipping comment fetch")
                return False

            if not task_report.plane_project_id or not task_report.plane_issue_id:
                bot_logger.warning(
                    f"⚠️ Missing project_id or issue_id for TaskReport #{task_report.id}"
                )
                return False

            bot_logger.info(
                f"📥 Fetching Plane data for issue {task_report.plane_issue_id}"
            )

            # Fetch issue details (for full description, assignees, project)
            issue_details = await plane_api.get_issue_details(
                project_id=task_report.plane_project_id,
                issue_id=task_report.plane_issue_id
            )

            # Fetch comments from Plane API
            comments = await plane_api.get_issue_comments(
                project_id=task_report.plane_project_id,
                issue_id=task_report.plane_issue_id
            )

            if not issue_details and not comments:
                bot_logger.info("ℹ️ No additional data from Plane API")
                return False

            # Update task_description if we got more details
            if issue_details and issue_details.get('description'):
                task_report.task_description = issue_details['description']
                bot_logger.info(f"✅ Updated task description from Plane API")

            # ═════════════════════════════════════════════════════════
            # AUTO-FILL METADATA FROM PLANE API
            # ═════════════════════════════════════════════════════════
            bot_logger.info(f"🔍 issue_details exists: {bool(issue_details)}, type: {type(issue_details)}")
            if issue_details:
                bot_logger.info(f"🔍 issue_details keys: {list(issue_details.keys()) if isinstance(issue_details, dict) else 'NOT A DICT'}")
                from ..modules.task_reports.utils import map_company_name

                # 1. Auto-fill COMPANY from project
                project_detail = issue_details.get('project_detail') or {}
                project_name = project_detail.get('name') or issue_details.get('project_name')

                # Get project identifier (HARZL, HHIVP, etc.) from project_detail
                project_identifier = project_detail.get('identifier') or issue_details.get('project_identifier')

                # If no project info in issue_details, fetch from Plane projects API
                if (not project_name or not project_identifier) and task_report.plane_project_id:
                    try:
                        bot_logger.info(f"📥 Fetching project details for {task_report.plane_project_id[:8]}")
                        projects = await plane_api.get_all_projects()
                        for proj in projects:
                            # projects is list of dicts, not objects
                            proj_id = proj.get('id') if isinstance(proj, dict) else proj.id
                            proj_name = proj.get('name') if isinstance(proj, dict) else proj.name
                            proj_identifier = proj.get('identifier') if isinstance(proj, dict) else getattr(proj, 'identifier', None)
                            if proj_id == task_report.plane_project_id:
                                project_name = proj_name
                                project_identifier = proj_identifier
                                bot_logger.info(f"✅ Found project: {project_name} ({project_identifier})")
                                break
                    except Exception as e:
                        bot_logger.warning(f"⚠️ Failed to fetch project details: {e}")

                # Save project_identifier to TaskReport
                if project_identifier and not task_report.project_identifier:
                    task_report.project_identifier = project_identifier
                    bot_logger.info(f"🏷️ Saved project_identifier: {project_identifier}")

                if project_name and not task_report.company:
                    # Map company name using COMPANY_MAPPING
                    mapped_company = map_company_name(project_name)
                    task_report.company = mapped_company
                    bot_logger.info(f"🏢 Auto-filled company: '{project_name}' → '{mapped_company}'")

                # 2. Auto-fill WORKERS from assignees OR closed_by
                assignees_raw = issue_details.get('assignees', [])
                bot_logger.info(f"🔍 assignees found: {len(assignees_raw)}, type: {type(assignees_raw)}")
                if assignees_raw:
                    bot_logger.info(f"🔍 First assignee: {assignees_raw[0] if assignees_raw else 'N/A'}")

                # Extract assignee data (can be list of dicts OR list of UUID strings)
                assignee_data = []
                if assignees_raw:
                    for a in assignees_raw:
                        if isinstance(a, dict):
                            # Assignee is already full object with name/email
                            assignee_data.append(a)
                        elif isinstance(a, str):
                            # Assignee is just UUID string, need to look up
                            assignee_data.append({'id': a})
                        else:
                            bot_logger.warning(f"⚠️ Unexpected assignee type: {type(a)}")

                # Fallback to closed_by if no assignees
                if not assignee_data and task_report.closed_by_plane_name:
                    bot_logger.info(f"🔄 No assignees, using closed_by: {task_report.closed_by_plane_name}")

                if (assignee_data or task_report.closed_by_plane_name) and not task_report.workers:
                    try:
                        worker_names = []

                        # Try to get workers from assignees first
                        if assignee_data:
                            bot_logger.info(f"👥 Processing {len(assignee_data)} assignees")

                            # Check if we need to fetch workspace members (only if assignees are UUID strings)
                            needs_lookup = any('display_name' not in a and 'email' not in a for a in assignee_data)

                            members_by_id = {}
                            if needs_lookup:
                                # Get workspace members to map UUIDs to names
                                workspace_members = await plane_api.get_workspace_members()
                                bot_logger.info(f"📥 Retrieved {len(workspace_members)} workspace members")

                                # Create ID -> member mapping (PlaneUser objects)
                                members_by_id = {}
                                for member in workspace_members:
                                    if hasattr(member, 'id'):
                                        # PlaneUser object
                                        members_by_id[member.id] = {
                                            'id': member.id,
                                            'display_name': member.display_name,
                                            'first_name': member.first_name,
                                            'email': member.email
                                        }
                                    elif isinstance(member, dict) and member.get('id'):
                                        # Dict format
                                        members_by_id[member['id']] = member

                            for assignee in assignee_data:
                                # Get assignee info (either from dict or lookup)
                                if 'display_name' in assignee or 'email' in assignee:
                                    # Already have full info
                                    name = assignee.get('display_name') or assignee.get('first_name', 'Unknown')
                                    email = assignee.get('email')
                                else:
                                    # Need to look up by ID
                                    assignee_id = assignee.get('id')
                                    member = members_by_id.get(assignee_id)
                                    if not member:
                                        bot_logger.warning(f"⚠️ Assignee {assignee_id[:8]}... not found in workspace")
                                        continue

                                    name = member.get('display_name') or member.get('first_name', 'Unknown')
                                    email = member.get('email')

                                # Map Plane user to Telegram (to get normalized names)
                                telegram_mapping = self.map_plane_user_to_telegram(
                                    plane_name=name,
                                    plane_email=email
                                )

                                # Use mapped telegram_username or original name
                                final_name = telegram_mapping.get('telegram_username') or name
                                worker_names.append(final_name)
                                bot_logger.info(f"👤 Mapped assignee: '{name}' → '{final_name}'")

                        # Fallback to closed_by if no assignees found
                        elif task_report.closed_by_plane_name:
                            bot_logger.info(f"🔄 Using closed_by as fallback: {task_report.closed_by_plane_name}")

                            # Map closed_by name through PLANE_TO_TELEGRAM_MAP
                            telegram_mapping = self.map_plane_user_to_telegram(
                                plane_name=task_report.closed_by_plane_name,
                                plane_email=None  # We don't have email for closed_by
                            )

                            # Use mapped telegram_username or original closed_by name
                            final_name = telegram_mapping.get('telegram_username') or task_report.closed_by_plane_name
                            worker_names.append(final_name)
                            bot_logger.info(f"👤 Mapped closed_by: '{task_report.closed_by_plane_name}' → '{final_name}'")

                        if worker_names:
                            import json
                            task_report.workers = json.dumps(worker_names, ensure_ascii=False)
                            bot_logger.info(f"👥 Auto-filled workers: {worker_names}")
                        else:
                            if assignee_ids:
                                bot_logger.warning(f"⚠️ No workers could be mapped from {len(assignee_ids)} assignees")
                            elif task_report.closed_by_plane_name:
                                bot_logger.warning(f"⚠️ Could not map closed_by: {task_report.closed_by_plane_name}")
                            else:
                                bot_logger.warning(f"⚠️ No assignees or closed_by found for task")

                    except Exception as e:
                        bot_logger.error(f"❌ Failed to auto-fill workers from assignees: {e}")

            # Generate report text from comments + description
            bot_logger.info(
                f"🔨 Generating report from: title={bool(task_report.task_title)}, "
                f"description={bool(task_report.task_description)}, "
                f"comments_count={len(comments) if comments else 0}"
            )

            report_text = await self._generate_report_text(
                title=task_report.task_title,
                description=task_report.task_description,
                comments=comments,
                sequence_id=task_report.plane_sequence_id,
                project_identifier=task_report.project_identifier
            )

            bot_logger.info(f"🔨 Generated report_text length: {len(report_text) if report_text else 0}")

            if report_text:
                task_report.report_text = report_text
                task_report.auto_filled_from_journal = True  # Mark as auto-generated
                task_report.status = "draft"  # Move to draft since we have content

                await session.commit()

                bot_logger.info(
                    f"✅ Auto-generated report for TaskReport #{task_report.id} "
                    f"from {len(comments)} comments"
                )
                return True
            else:
                bot_logger.info("ℹ️ No content to generate report from")
                return False

        except Exception as e:
            bot_logger.error(f"❌ Error fetching from Plane API: {e}")
            return False

    async def _generate_report_text(
        self,
        title: Optional[str],
        description: Optional[str],
        comments: List[Dict],
        sequence_id: Optional[int],
        project_identifier: Optional[str] = None
    ) -> str:
        """
        Generate user-friendly report text from Plane data

        Args:
            title: Task title
            description: Task description
            comments: List of comment objects
            sequence_id: Task sequence number (82, 123, etc.)
            project_identifier: Project prefix (HARZL, HHIVP, etc.)

        Returns:
            Formatted report text
        """
        report_lines = []

        # Header (no markdown - will be displayed in HTML mode)
        if sequence_id:
            # Use project_identifier if available, otherwise fallback to HHIVP
            prefix = project_identifier or "HHIVP"
            report_lines.append(f"📋 Отчёт по задаче {prefix}-{sequence_id}\n")
        else:
            report_lines.append(f"📋 Отчёт по выполненной задаче\n")

        # Task title
        if title:
            report_lines.append(f"Задача: {title}\n")

        # Description (if meaningful)
        if description and len(description.strip()) > 10:
            report_lines.append(f"Описание:\n{description}\n")

        # Comments (main content)
        if comments:
            report_lines.append(f"Выполненные работы:\n")
            bot_logger.info(f"🔨 Processing {len(comments)} comments for report generation")

            # FETCH workspace members ONCE for UUID → name mapping
            members_by_id = {}
            try:
                from ..integrations.plane import plane_api
                if plane_api.configured:
                    workspace_members = await plane_api.get_workspace_members()
                    bot_logger.info(f"📥 Retrieved {len(workspace_members)} workspace members for comment authors")

                    for member in workspace_members:
                        if hasattr(member, 'id'):
                            members_by_id[member.id] = {
                                'display_name': member.display_name,
                                'first_name': member.first_name,
                                'email': member.email
                            }
                        elif isinstance(member, dict) and member.get('id'):
                            members_by_id[member['id']] = member
            except Exception as e:
                bot_logger.warning(f"⚠️ Failed to fetch workspace members for comments: {e}")

            for idx, comment in enumerate(comments, 1):
                # Debug: Log full comment structure
                bot_logger.debug(f"  Comment {idx} RAW keys: {list(comment.keys())}")
                bot_logger.debug(f"  Comment {idx} FULL: {comment}")

                comment_html = comment.get('comment_html', '').strip()
                comment_plain = comment.get('comment', '').strip()  # BUG FIX #1: Fallback to plain comment
                bot_logger.debug(
                    f"  Comment {idx}: comment_html_type={type(comment_html)}, "
                    f"comment_plain_type={type(comment_plain)}"
                )

                # BUG FIX #1: Try comment_html first, then fall back to comment field
                if not comment_html and not comment_plain:
                    bot_logger.warning(f"  ⚠️ Comment {idx} has no content, skipping")
                    continue

                # Strip HTML tags from comment
                import re
                if comment_html:
                    comment_text = re.sub(r'<[^>]+>', '', comment_html).strip()
                else:
                    comment_text = comment_plain  # Use plain comment as fallback

                if not comment_text:
                    continue

                # Extract actor name (try multiple paths in Plane API)
                # BUG FIX: actor/created_by can be UUID strings, not dicts
                actor_detail = comment.get('actor_detail', {})
                actor = comment.get('actor', {})
                created_by = comment.get('created_by', {})

                actor_name = None
                actor_email = None

                # Try actor_detail first (usually has full info)
                if isinstance(actor_detail, dict) and actor_detail:
                    actor_name = actor_detail.get('display_name') or actor_detail.get('first_name')
                    actor_email = actor_detail.get('email')

                # Try actor if actor_detail didn't work
                if not actor_name:
                    if isinstance(actor, dict) and actor:
                        actor_name = actor.get('display_name') or actor.get('first_name')
                        actor_email = actor.get('email')
                    elif isinstance(actor, str) and len(actor) > 20:
                        # actor is a UUID string - look it up
                        member = members_by_id.get(actor)
                        if member:
                            actor_name = member.get('display_name') or member.get('first_name')
                            actor_email = member.get('email')
                            bot_logger.debug(f"  🔍 Resolved actor UUID {actor[:8]}... to {actor_name}")

                # Try created_by if still no name
                if not actor_name:
                    if isinstance(created_by, dict) and created_by:
                        actor_name = created_by.get('display_name') or created_by.get('first_name')
                        actor_email = created_by.get('email')
                    elif isinstance(created_by, str) and len(created_by) > 20:
                        # created_by is a UUID string - look it up
                        member = members_by_id.get(created_by)
                        if member:
                            actor_name = member.get('display_name') or member.get('first_name')
                            actor_email = member.get('email')
                            bot_logger.debug(f"  🔍 Resolved created_by UUID {created_by[:8]}... to {actor_name}")

                # Apply PLANE_TO_TELEGRAM_MAP to normalize names (Константин Макейкин → zardes)
                if actor_name:
                    telegram_mapping = self.map_plane_user_to_telegram(
                        plane_name=actor_name,
                        plane_email=actor_email
                    )
                    # Use mapped telegram_username or keep original name
                    mapped_name = telegram_mapping.get('telegram_username')
                    if mapped_name:
                        bot_logger.debug(f"  📝 Mapped comment author: '{actor_name}' → '{mapped_name}'")
                        actor_name = mapped_name

                # Fallback to Unknown
                if not actor_name:
                    actor_name = 'Unknown'
                    bot_logger.warning(
                        f"⚠️ Could not extract author name from comment. "
                        f"actor_detail={type(actor_detail)}, actor={type(actor)}, created_by={type(created_by)}"
                    )

                # Extract timestamp
                created_at = comment.get('created_at', '')
                if created_at:
                    try:
                        dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        date_str = dt.strftime("%d.%m.%Y %H:%M")
                    except:
                        date_str = created_at[:10]
                else:
                    date_str = ''

                # Format comment
                report_lines.append(
                    f"{idx}. [{actor_name}] {date_str}\n"
                    f"   {comment_text}\n"
                )

        # Only reject if we have ONLY header (no title) or empty
        # Header + title is still meaningful (shows task completion)
        if len(report_lines) <= 1:
            bot_logger.warning(
                f"⚠️ Report has only {len(report_lines)} lines (header only), "
                f"returning empty. Lines: {report_lines}"
            )
            return ""  # No meaningful content

        final_report = "\n".join(report_lines)
        bot_logger.info(
            f"✅ Generated report with {len(report_lines)} lines, "
            f"total length: {len(final_report)} chars"
        )
        return final_report

    # ═══════════════════════════════════════════════════════════
    # AUTO-FILL FROM WORK JOURNAL (FALLBACK)
    # ═══════════════════════════════════════════════════════════

    async def try_autofill_from_work_journal(
        self,
        session: AsyncSession,
        task_report: TaskReport
    ) -> bool:
        """
        Try to auto-fill report text from recent work_journal entries

        Searches for entries:
        - Linked to same support_request_id
        - Mentioning plane_sequence_id in description
        - Created in last 7 days

        Returns:
            True if autofilled, False otherwise
        """
        try:
            # Search criteria
            search_conditions = []

            # NOTE: WorkJournalEntry does not have support_request_id field
            # Only search by plane_sequence_id mention in work_description

            # By plane_sequence_id mention in work_description
            if task_report.plane_sequence_id:
                search_conditions.append(
                    WorkJournalEntry.work_description.ilike(f"%{task_report.plane_sequence_id}%")
                )

            if not search_conditions:
                bot_logger.info("ℹ️ No search criteria for autofill")
                return False

            # Date range: last 7 days
            week_ago = datetime.now(timezone.utc) - timedelta(days=7)

            # Query
            result = await session.execute(
                select(WorkJournalEntry)
                .where(
                    and_(
                        or_(*search_conditions),
                        WorkJournalEntry.created_at >= week_ago
                    )
                )
                .order_by(WorkJournalEntry.created_at.desc())
                .limit(5)
            )
            entries = result.scalars().all()

            if not entries:
                bot_logger.info(
                    f"ℹ️ No work_journal entries found for autofill "
                    f"(plane_seq={task_report.plane_sequence_id})"
                )
                return False

            # Build report text from entries (no markdown - displayed in HTML mode)
            report_lines = [
                f"Выполненные работы по задаче #{task_report.plane_sequence_id}:\n"
            ]

            for entry in entries:
                # Дата работы
                date_str = entry.work_date.strftime("%d.%m.%Y")

                # Часы работы
                duration_str = entry.work_duration

                # Тип работы (выезд/удаленно)
                work_type = "🚗 Выезд" if entry.is_travel else "💻 Удаленно"

                # Исполнители (парсим JSON)
                try:
                    workers = json.loads(entry.worker_names)
                    workers_str = ", ".join(workers) if isinstance(workers, list) else entry.worker_names
                except:
                    workers_str = entry.worker_names

                # Компания
                company_str = entry.company

                # Описание работы
                work_desc = entry.work_description

                # Формируем запись
                report_lines.append(
                    f"📅 {date_str} | {work_type} | ⏱️ {duration_str}\n"
                    f"🏢 Компания: {company_str}\n"
                    f"👥 Исполнители: {workers_str}\n"
                    f"📝 Описание:\n{work_desc}\n"
                )

            autofilled_text = "\n".join(report_lines)

            # Update task_report
            task_report.report_text = autofilled_text
            task_report.auto_filled_from_journal = True
            task_report.status = "draft"  # Move to draft since we have content

            # Link to first entry (for reference)
            if entries:
                task_report.work_journal_entry_id = entries[0].id

            await session.commit()

            bot_logger.info(
                f"✅ Auto-filled TaskReport #{task_report.id} from "
                f"{len(entries)} work_journal entries"
            )
            return True

        except Exception as e:
            bot_logger.error(f"❌ Error auto-filling from work_journal: {e}")
            return False

    # ═══════════════════════════════════════════════════════════
    # REPORT STATUS MANAGEMENT
    # ═══════════════════════════════════════════════════════════

    async def update_report_text(
        self,
        session: AsyncSession,
        task_report_id: int,
        report_text: str,
        submitted_by_telegram_id: int
    ) -> Optional[TaskReport]:
        """
        Update report text (admin filled/edited report)

        Args:
            task_report_id: TaskReport ID
            report_text: New report text
            submitted_by_telegram_id: Telegram ID of admin who submitted

        Returns:
            Updated TaskReport or None
        """
        try:
            task_report = await self.get_task_report(session, task_report_id)
            if not task_report:
                return None

            task_report.report_text = report_text
            task_report.report_submitted_by = submitted_by_telegram_id
            task_report.report_submitted_at = datetime.now(timezone.utc)
            task_report.status = "draft"  # Move to draft for review

            await session.commit()
            await session.refresh(task_report)

            bot_logger.info(
                f"✅ Updated report text for TaskReport #{task_report_id}"
            )
            return task_report

        except Exception as e:
            bot_logger.error(f"❌ Error updating report text: {e}")
            await session.rollback()
            return None

    async def update_metadata(
        self,
        session: AsyncSession,
        task_report_id: int,
        work_duration: Optional[str] = None,
        is_travel: Optional[bool] = None,
        company: Optional[str] = None,
        workers: Optional[str] = None  # JSON string
    ) -> Optional[TaskReport]:
        """
        Update task report metadata (duration, work_type, company, workers)

        Args:
            task_report_id: TaskReport ID
            work_duration: Duration string (e.g., "2h", "4h")
            is_travel: True if travel, False if remote
            company: Company name
            workers: JSON string with list of workers

        Returns:
            Updated TaskReport or None
        """
        try:
            task_report = await self.get_task_report(session, task_report_id)
            if not task_report:
                return None

            # Update fields if provided
            if work_duration is not None:
                task_report.work_duration = work_duration
                bot_logger.info(f"📝 Updated duration: {work_duration}")

            if is_travel is not None:
                task_report.is_travel = is_travel
                bot_logger.info(f"📝 Updated is_travel: {is_travel}")

            if company is not None:
                task_report.company = company
                bot_logger.info(f"📝 Updated company: {company}")

            if workers is not None:
                task_report.workers = workers
                bot_logger.info(f"📝 Updated workers: {workers}")

            await session.commit()
            await session.refresh(task_report)

            bot_logger.info(
                f"✅ Updated metadata for TaskReport #{task_report_id}"
            )
            return task_report

        except Exception as e:
            bot_logger.error(f"❌ Error updating metadata: {e}")
            await session.rollback()
            return None

    async def approve_report(
        self,
        session: AsyncSession,
        task_report_id: int
    ) -> Optional[TaskReport]:
        """
        Approve report - ready to send to client

        Returns:
            Updated TaskReport or None
        """
        try:
            task_report = await self.get_task_report(session, task_report_id)
            if not task_report:
                return None

            if not task_report.report_text:
                bot_logger.error(
                    f"❌ Cannot approve TaskReport #{task_report_id} - no report text"
                )
                return None

            task_report.status = "approved"
            await session.commit()
            await session.refresh(task_report)

            bot_logger.info(f"✅ Approved TaskReport #{task_report_id}")
            return task_report

        except Exception as e:
            bot_logger.error(f"❌ Error approving report: {e}")
            await session.rollback()
            return None

    async def mark_sent_to_client(
        self,
        session: AsyncSession,
        task_report_id: int
    ) -> Optional[TaskReport]:
        """
        Mark report as sent to client

        Returns:
            Updated TaskReport or None
        """
        try:
            task_report = await self.get_task_report(session, task_report_id)
            if not task_report:
                return None

            task_report.status = "sent_to_client"
            task_report.client_notified_at = datetime.now(timezone.utc)

            await session.commit()
            await session.refresh(task_report)

            bot_logger.info(f"✅ Marked TaskReport #{task_report_id} as sent to client")
            return task_report

        except Exception as e:
            bot_logger.error(f"❌ Error marking report as sent: {e}")
            await session.rollback()
            return None

    async def close_without_report(
        self,
        session: AsyncSession,
        task_report_id: int
    ) -> Optional[TaskReport]:
        """
        Close task report without sending to client

        Admin decision to skip client notification. This is used when:
        - No client is linked to the task
        - Internal task (no client notification needed)
        - Admin decides not to send report

        Returns:
            Updated TaskReport or None
        """
        try:
            task_report = await self.get_task_report(session, task_report_id)
            if not task_report:
                return None

            task_report.status = "cancelled"

            await session.commit()
            await session.refresh(task_report)

            bot_logger.info(
                f"✅ Closed TaskReport #{task_report_id} without sending to client "
                f"(Plane task #{task_report.plane_sequence_id})"
            )
            return task_report

        except Exception as e:
            bot_logger.error(f"❌ Error closing report without notification: {e}")
            await session.rollback()
            return None

    # ═══════════════════════════════════════════════════════════
    # REMINDER SYSTEM
    # ═══════════════════════════════════════════════════════════

    async def get_pending_reports(
        self,
        session: AsyncSession
    ) -> List[TaskReport]:
        """
        Get all pending task reports (not yet filled)

        Returns:
            List of pending TaskReport objects
        """
        try:
            result = await session.execute(
                select(TaskReport)
                .where(TaskReport.status == "pending")
                .order_by(TaskReport.closed_at.asc())
            )
            return result.scalars().all()

        except Exception as e:
            bot_logger.error(f"❌ Error getting pending reports: {e}")
            return []

    async def update_reminder_sent(
        self,
        session: AsyncSession,
        task_report_id: int,
        reminder_level: int
    ) -> Optional[TaskReport]:
        """
        Update reminder count and level after sending reminder

        Args:
            task_report_id: TaskReport ID
            reminder_level: New reminder level (0-3)

        Returns:
            Updated TaskReport or None
        """
        try:
            task_report = await self.get_task_report(session, task_report_id)
            if not task_report:
                return None

            task_report.reminder_count += 1
            task_report.last_reminder_at = datetime.now(timezone.utc)
            task_report.reminder_level = reminder_level

            await session.commit()
            await session.refresh(task_report)

            bot_logger.info(
                f"📨 Updated reminder for TaskReport #{task_report_id}: "
                f"count={task_report.reminder_count}, level={reminder_level}"
            )
            return task_report

        except Exception as e:
            bot_logger.error(f"❌ Error updating reminder: {e}")
            await session.rollback()
            return None

    # ═══════════════════════════════════════════════════════════
    # QUERY HELPERS
    # ═══════════════════════════════════════════════════════════

    async def get_task_report(
        self,
        session: AsyncSession,
        task_report_id: int
    ) -> Optional[TaskReport]:
        """Get TaskReport by ID"""
        try:
            result = await session.execute(
                select(TaskReport).where(TaskReport.id == task_report_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            bot_logger.error(f"❌ Error getting task report: {e}")
            return None

    async def get_task_report_by_plane_issue(
        self,
        session: AsyncSession,
        plane_issue_id: str
    ) -> Optional[TaskReport]:
        """Get TaskReport by Plane issue ID"""
        try:
            result = await session.execute(
                select(TaskReport).where(TaskReport.plane_issue_id == plane_issue_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            bot_logger.error(f"❌ Error getting task report by plane issue: {e}")
            return None

    async def get_support_request(
        self,
        session: AsyncSession,
        support_request_id: int
    ) -> Optional[SupportRequest]:
        """Get SupportRequest by ID"""
        try:
            result = await session.execute(
                select(SupportRequest).where(SupportRequest.id == support_request_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            bot_logger.error(f"❌ Error getting support request: {e}")
            return None

    # ═══════════════════════════════════════════════════════════
    # UTILITY METHODS
    # ═══════════════════════════════════════════════════════════

    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Parse ISO datetime string to datetime object"""
        if not dt_str:
            return None
        try:
            # Handle ISO format with Z
            if dt_str.endswith('Z'):
                dt_str = dt_str[:-1] + '+00:00'
            return datetime.fromisoformat(dt_str)
        except Exception as e:
            bot_logger.error(f"❌ Error parsing datetime '{dt_str}': {e}")
            return None

    def _format_duration(self, minutes: Optional[int]) -> str:
        """Format duration in minutes to human-readable string"""
        if not minutes:
            return "0 минут"

        hours = minutes // 60
        mins = minutes % 60

        if hours > 0 and mins > 0:
            return f"{hours} ч {mins} мин"
        elif hours > 0:
            return f"{hours} ч"
        else:
            return f"{mins} мин"


# Global singleton instance
task_reports_service = TaskReportsService()
