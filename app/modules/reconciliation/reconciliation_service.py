"""
Daily Chat Reconciliation Service.

Analyzes today's messages from linked group chats,
extracts incidents via AI, matches to Plane tasks,
and proposes actions (close/create).
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, date, time, timezone
from typing import Optional

import aiohttp
import pytz

from ...config import settings
from ...database.database import get_async_session
from ...services.chat_context_service import chat_context_service
from ...services.support_requests_service import support_requests_service
from ...services.plane_mappings_service import PlaneMappingsService
from ...integrations.plane import plane_api
from ..plane_assistant import plane_service
from ...core.ai.ai_manager import ai_manager
from ...utils.logger import bot_logger
from .ai_prompts import EXTRACTION_PROMPT


AI_TIMEOUT = 45
AI_PROVIDERS = ["groq", "openrouter"]


@dataclass
class ExtractedIncident:
    title: str
    description: str
    is_resolved: bool
    resolution_summary: Optional[str] = None
    mentioned_users: list[str] = field(default_factory=list)
    estimated_duration: Optional[str] = None
    confidence: float = 0.0


@dataclass
class ReconciliationItem:
    chat_id: int
    chat_title: str
    plane_project_id: str
    plane_project_name: str
    incident: ExtractedIncident
    matching_plane_task: Optional[dict] = None
    proposed_action: str = ""  # close_existing | create_done | create_started | none
    work_journal_company: Optional[str] = None


def serialize_item(item: ReconciliationItem) -> dict:
    return {
        "chat_id": item.chat_id,
        "chat_title": item.chat_title,
        "plane_project_id": item.plane_project_id,
        "plane_project_name": item.plane_project_name,
        "incident": {
            "title": item.incident.title,
            "description": item.incident.description,
            "is_resolved": item.incident.is_resolved,
            "resolution_summary": item.incident.resolution_summary,
            "mentioned_users": item.incident.mentioned_users,
            "estimated_duration": item.incident.estimated_duration,
        },
        "matching_plane_task": item.matching_plane_task,
        "proposed_action": item.proposed_action,
        "work_journal_company": item.work_journal_company,
    }


def deserialize_item(data: dict) -> ReconciliationItem:
    inc = data["incident"]
    return ReconciliationItem(
        chat_id=data["chat_id"],
        chat_title=data["chat_title"],
        plane_project_id=data["plane_project_id"],
        plane_project_name=data["plane_project_name"],
        incident=ExtractedIncident(
            title=inc["title"],
            description=inc["description"],
            is_resolved=inc["is_resolved"],
            resolution_summary=inc.get("resolution_summary"),
            mentioned_users=inc.get("mentioned_users", []),
            estimated_duration=inc.get("estimated_duration"),
        ),
        matching_plane_task=data.get("matching_plane_task"),
        proposed_action=data.get("proposed_action", ""),
        work_journal_company=data.get("work_journal_company"),
    )


class ReconciliationService:

    async def run(self) -> list[ReconciliationItem]:
        """Main entry: analyze all linked chats for today."""
        items = []

        async for session in get_async_session():
            mappings = await support_requests_service.list_all_mappings(
                session, only_active=True
            )

        if not mappings:
            bot_logger.info("Reconciliation: no linked chats found")
            return []

        bot_logger.info(f"Reconciliation: processing {len(mappings)} linked chats")

        for mapping in mappings:
            try:
                chat_items = await self._process_chat(mapping)
                items.extend(chat_items)
            except Exception as e:
                bot_logger.error(
                    f"Reconciliation error for chat {mapping.chat_title}: {e}"
                )

        bot_logger.info(
            f"Reconciliation done: {len(items)} incidents from {len(mappings)} chats"
        )
        return items

    async def _process_chat(self, mapping) -> list[ReconciliationItem]:
        """Process a single linked chat."""
        tz = pytz.timezone(settings.daily_tasks_timezone)
        today_start = datetime.combine(date.today(), time.min, tzinfo=tz)
        today_start_utc = today_start.astimezone(timezone.utc).replace(tzinfo=None)

        chat_log = await chat_context_service.get_context_as_text(
            chat_id=mapping.chat_id, since=today_start_utc
        )

        if not chat_log or len(chat_log.strip()) < 30:
            return []

        incidents = await self._extract_incidents(
            chat_log, mapping.chat_title or str(mapping.chat_id)
        )
        if not incidents:
            return []

        project_tasks = await self._get_project_tasks(mapping.plane_project_id)

        company_name = None
        try:
            async for session in get_async_session():
                svc = PlaneMappingsService(session)
                company_name = await svc.get_company_display_name(
                    mapping.plane_project_name or ""
                )
        except Exception:
            company_name = mapping.plane_project_name

        items = []
        for incident in incidents:
            item = ReconciliationItem(
                chat_id=mapping.chat_id,
                chat_title=mapping.chat_title or str(mapping.chat_id),
                plane_project_id=mapping.plane_project_id,
                plane_project_name=mapping.plane_project_name or "?",
                incident=incident,
                work_journal_company=company_name,
            )

            matched = self._fuzzy_match_task(incident.title, project_tasks)
            if matched:
                item.matching_plane_task = matched
                item.proposed_action = (
                    "close_existing" if incident.is_resolved else "none"
                )
            else:
                item.proposed_action = (
                    "create_done" if incident.is_resolved else "create_started"
                )

            if item.proposed_action != "none":
                items.append(item)

        return items

    async def _extract_incidents(
        self, chat_log: str, chat_title: str
    ) -> list[ExtractedIncident]:
        """Call AI to extract incidents from chat log."""
        system = EXTRACTION_PROMPT.format(chat_title=chat_title)

        response_text = await self._call_ai(
            f"Лог чата за сегодня:\n\n{chat_log}\n\nИзвлеки все инциденты/заявки.",
            system,
        )

        if not response_text:
            return []

        return self._parse_incidents_json(response_text)

    async def _call_ai(self, user_message: str, system_prompt: str) -> Optional[str]:
        """Call AI with multi-provider fallback."""
        for provider_name in AI_PROVIDERS:
            provider = ai_manager.get_provider(provider_name)
            if not provider:
                continue
            try:
                response = await asyncio.wait_for(
                    ai_manager.chat(
                        user_message=user_message,
                        system_prompt=system_prompt,
                        provider_name=provider_name,
                    ),
                    timeout=AI_TIMEOUT,
                )
                content = (
                    response.content if hasattr(response, "content") else str(response)
                )
                bot_logger.info(
                    f"Reconciliation AI via {provider_name} ({len(content)} chars)"
                )
                return content
            except asyncio.TimeoutError:
                bot_logger.warning(f"Reconciliation AI timeout on {provider_name}")
            except Exception as e:
                bot_logger.warning(f"Reconciliation AI error on {provider_name}: {e}")

        return None

    def _parse_incidents_json(self, text: str) -> list[ExtractedIncident]:
        """Parse AI response JSON into ExtractedIncident list."""
        # Try ```json block
        m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        raw = m.group(1).strip() if m else text.strip()

        # Try to find JSON object
        if not raw.startswith("{"):
            m2 = re.search(r"\{.*\}", raw, re.DOTALL)
            if m2:
                raw = m2.group()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            bot_logger.warning(f"Reconciliation: failed to parse AI JSON: {raw[:200]}")
            return []

        incidents_raw = data.get("incidents", [])
        result = []
        for inc in incidents_raw:
            if not inc.get("title"):
                continue
            result.append(
                ExtractedIncident(
                    title=inc["title"],
                    description=inc.get("description", ""),
                    is_resolved=inc.get("is_resolved", False),
                    resolution_summary=inc.get("resolution_summary"),
                    mentioned_users=inc.get("mentioned_users", []),
                    estimated_duration=inc.get("estimated_duration"),
                    confidence=inc.get("confidence", 0.5),
                )
            )
        return result

    async def _get_project_tasks(self, project_id: str) -> list[dict]:
        """Get open tasks from Plane for a project."""
        try:
            async with aiohttp.ClientSession() as session:
                tasks = await plane_api._tasks_manager._get_project_issues(
                    session, project_id, assigned_only=False
                )
                return [
                    {
                        "id": t.id,
                        "name": t.name,
                        "sequence_id": t.sequence_id,
                        "state": t.get_state_name(),
                        "priority": t.priority,
                    }
                    for t in (tasks or [])
                ]
        except Exception as e:
            bot_logger.warning(f"Reconciliation: failed to get project tasks: {e}")
            return []

    def _fuzzy_match_task(
        self, incident_title: str, tasks: list[dict]
    ) -> Optional[dict]:
        """Fuzzy match incident title to existing Plane tasks."""
        title_lower = incident_title.lower()
        words = [w for w in title_lower.split() if len(w) > 3]

        best_match = None
        best_score = 0

        for task in tasks:
            task_name_lower = task["name"].lower()

            # Exact substring
            if title_lower in task_name_lower or task_name_lower in title_lower:
                return task

            # Word overlap
            score = sum(1 for w in words if w in task_name_lower)
            if score > best_score and score >= max(2, len(words) // 2):
                best_score = score
                best_match = task

        return best_match

    # === Action execution ===

    async def execute_action(self, item: ReconciliationItem) -> tuple[bool, str]:
        """Execute proposed action. Returns (success, message)."""
        action = item.proposed_action
        title = item.incident.title

        try:
            if action == "close_existing" and item.matching_plane_task:
                ok = await plane_service.close_issue(
                    item.plane_project_id, item.matching_plane_task["id"]
                )
                seq = item.matching_plane_task.get("sequence_id", "?")
                return ok, (
                    f"#{seq} закрыта" if ok else f"#{seq} ошибка закрытия"
                )

            elif action == "create_done":
                result = await plane_api.create_issue(
                    project_id=item.plane_project_id,
                    name=title,
                    description=item.incident.description,
                )
                if result:
                    issue_id = result.get("id") or (result["id"] if isinstance(result, dict) else None)
                    if issue_id:
                        await plane_service.close_issue(
                            item.plane_project_id, issue_id
                        )
                    seq = result.get("sequence_id", "?")
                    return True, f"создана #{seq} (Done)"
                return False, f"ошибка создания '{title[:30]}'"

            elif action == "create_started":
                result = await plane_api.create_issue(
                    project_id=item.plane_project_id,
                    name=title,
                    description=item.incident.description,
                )
                if result:
                    issue_id = result.get("id")
                    if issue_id:
                        await plane_service.change_status(
                            item.plane_project_id, issue_id, "started"
                        )
                    seq = result.get("sequence_id", "?")
                    return True, f"создана #{seq} (Started)"
                return False, f"ошибка создания '{title[:30]}'"

            else:
                return False, f"неизвестное действие: {action}"

        except Exception as e:
            bot_logger.error(f"Reconciliation execute error: {e}")
            return False, f"ошибка: {str(e)[:50]}"
