"""
Task Reports Service - Business logic for client task reports

When a task is completed in Plane, this service:
1. Creates TaskReport from webhook data
2. Maps Plane user to Telegram admin
3. Auto-fills report from work_journal if available
4. Manages report status transitions
5. Sends reports to clients
"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

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
        "Zardes": {
            "telegram_username": "zardes",
            "telegram_id": 28795547
        },
        "zarudesu@gmail.com": {
            "telegram_username": "zardes",
            "telegram_id": 28795547
        },
        # Add more admins here as needed
        # "Another Admin": {
        #     "telegram_username": "username",
        #     "telegram_id": 123456789
        # }
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
                bot_logger.warning(
                    f"⚠️ TaskReport already exists for plane_issue_id={plane_issue_id}"
                )
                return existing

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

            # Try to autofill from work_journal
            await self.try_autofill_from_work_journal(session, task_report)

            return task_report

        except Exception as e:
            bot_logger.error(f"❌ Error creating TaskReport from webhook: {e}")
            await session.rollback()
            return None

    # ═══════════════════════════════════════════════════════════
    # AUTO-FILL FROM WORK JOURNAL
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

            # 1. By support_request_id (if available)
            if task_report.support_request_id:
                search_conditions.append(
                    WorkJournalEntry.support_request_id == task_report.support_request_id
                )

            # 2. By plane_sequence_id mention in description
            if task_report.plane_sequence_id:
                search_conditions.append(
                    WorkJournalEntry.description.ilike(f"%{task_report.plane_sequence_id}%")
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
                    f"(support_request_id={task_report.support_request_id}, "
                    f"plane_seq={task_report.plane_sequence_id})"
                )
                return False

            # Build report text from entries
            report_lines = [
                f"**Выполненные работы по задаче #{task_report.plane_sequence_id}:**\n"
            ]

            for entry in entries:
                date_str = entry.created_at.strftime("%d.%m.%Y")
                duration_str = self._format_duration(entry.duration_minutes)
                report_lines.append(
                    f"📅 {date_str} ({duration_str}):\n{entry.description}\n"
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
