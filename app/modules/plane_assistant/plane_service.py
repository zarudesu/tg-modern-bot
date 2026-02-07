"""Plane data layer for /plane assistant.

Collects data from Plane API and prepares it for AI analysis.
"""

import aiohttp
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple

from ...integrations.plane import plane_api, PlaneTask
from ...services.redis_service import redis_service
from ...utils.logger import bot_logger

CACHE_TTL = 300  # 5 min


async def get_my_tasks_summary(user_email: str) -> str:
    """Get all open tasks for user, formatted as text for AI."""
    tasks = await plane_api.get_user_tasks(user_email)
    if not tasks:
        return "У пользователя нет открытых задач."

    now = datetime.now(timezone.utc)
    lines = []
    for t in tasks:
        overdue = ""
        if t.target_date:
            try:
                td = datetime.fromisoformat(t.target_date).replace(tzinfo=timezone.utc)
                if td < now:
                    days = (now - td).days
                    overdue = f" [ПРОСРОЧЕНО на {days} дн!]"
            except (ValueError, TypeError):
                pass

        stale = ""
        if t.updated_at:
            try:
                upd = datetime.fromisoformat(t.updated_at.replace('Z', '+00:00'))
                days_since = (now - upd).days
                if days_since > 14:
                    stale = f" [не обновлялась {days_since} дн]"
            except (ValueError, TypeError):
                pass

        lines.append(
            f"- #{t.sequence_id} [{t.project_name}/{t.get_state_name()}] "
            f"P:{t.priority or 'none'} | {t.name[:80]}{overdue}{stale}"
        )

    return f"Открытых задач: {len(tasks)}\n" + "\n".join(lines)


async def get_project_tasks_summary(project_identifier: str) -> str:
    """Get all open tasks for a project."""
    projects = await plane_api.get_all_projects()
    if not projects:
        return "Не удалось загрузить проекты."

    project = None
    for p in projects:
        if project_identifier.upper() in (
            p.get('identifier', '').upper(),
            p.get('name', '').upper()
        ):
            project = p
            break

    if not project:
        names = [f"{p.get('identifier', '?')} ({p.get('name', '')})" for p in projects[:15]]
        return f"Проект '{project_identifier}' не найден. Доступные проекты:\n" + "\n".join(names)

    pid = project['id']
    pname = project.get('identifier', '?')

    try:
        async with aiohttp.ClientSession() as session:
            tasks = await plane_api._tasks_manager._get_project_issues(
                session, pid, assigned_only=False
            )
    except Exception as e:
        return f"Ошибка загрузки задач проекта {pname}: {e}"

    if not tasks:
        return f"В проекте {pname} нет открытых задач."

    lines = []
    for t in tasks:
        lines.append(
            f"- #{t.sequence_id} [{t.get_state_name()}] P:{t.priority or 'none'} "
            f"| {t.name[:70]} | {t.assignee_name}"
        )

    return f"Проект {pname}: {len(tasks)} открытых задач\n" + "\n".join(lines)


async def get_overdue_summary(user_email: str) -> str:
    """Get overdue and stale tasks."""
    tasks = await plane_api.get_user_tasks(user_email)
    if not tasks:
        return "Нет открытых задач."

    now = datetime.now(timezone.utc)
    overdue = []
    stale_in_progress = []

    for t in tasks:
        if t.target_date:
            try:
                td = datetime.fromisoformat(t.target_date).replace(tzinfo=timezone.utc)
                if td < now:
                    days = (now - td).days
                    overdue.append((days, t))
            except (ValueError, TypeError):
                pass

        state_name = t.get_state_name().lower()
        if state_name in ('in progress', 'in_progress', 'started'):
            if t.updated_at:
                try:
                    upd = datetime.fromisoformat(t.updated_at.replace('Z', '+00:00'))
                    days_since = (now - upd).days
                    if days_since > 14:
                        stale_in_progress.append((days_since, t))
                except (ValueError, TypeError):
                    pass

    lines = []
    if overdue:
        overdue.sort(key=lambda x: -x[0])
        lines.append(f"ПРОСРОЧЕННЫЕ ({len(overdue)}):")
        for days, t in overdue[:15]:
            lines.append(
                f"  - #{t.sequence_id} [{t.project_name}] на {days} дн. | {t.name[:60]}"
            )

    if stale_in_progress:
        stale_in_progress.sort(key=lambda x: -x[0])
        lines.append(f"\nЗАВИСШИЕ In Progress ({len(stale_in_progress)}):")
        for days, t in stale_in_progress[:15]:
            lines.append(
                f"  - #{t.sequence_id} [{t.project_name}] {days} дн. без обновления | {t.name[:60]}"
            )

    if not lines:
        return "Нет просроченных или зависших задач."

    return "\n".join(lines)


async def get_workload_summary() -> str:
    """Get team workload distribution."""
    members = await plane_api.get_workspace_members()
    if not members:
        return "Не удалось загрузить участников."

    lines = []
    for member in members:
        email = member.email if hasattr(member, 'email') else member.get('email', '')
        name = member.display_name if hasattr(member, 'display_name') else member.get('display_name', email)
        if not email or email == 'info@hhivp.com':
            continue
        try:
            tasks = await plane_api.get_user_tasks(email)
            count = len(tasks) if tasks else 0
            urgent = sum(1 for t in (tasks or []) if t.priority in ('urgent', 'high'))
            lines.append(f"- {name}: {count} задач ({urgent} срочных)")
        except Exception:
            lines.append(f"- {name}: ошибка загрузки")

    return "Нагрузка команды:\n" + "\n".join(lines)


async def get_projects_list() -> str:
    """Get all projects."""
    projects = await plane_api.get_all_projects()
    if not projects:
        return "Не удалось загрузить проекты."

    lines = []
    for p in projects:
        lines.append(f"- {p.get('identifier', '?')}: {p.get('name', '?')}")
    return f"Проекты ({len(projects)}):\n" + "\n".join(lines)


async def find_issue_by_seq(seq_id: int) -> Optional[Tuple[str, str, dict]]:
    """Find issue across all projects by sequence_id.

    Returns (project_id, project_identifier, issue_data) or None.
    """
    cache_key = f"plane_seq:{seq_id}"
    cached = await redis_service.get_json(cache_key)
    if cached:
        return cached["project_id"], cached["project_ident"], cached["issue"]

    projects = await plane_api.get_all_projects()
    if not projects:
        return None

    for p in projects:
        pid = p['id']
        pident = p.get('identifier', '?')
        try:
            async with aiohttp.ClientSession() as session:
                tasks = await plane_api._tasks_manager._get_project_issues(
                    session, pid, assigned_only=False
                )
                for t in tasks:
                    if t.sequence_id == seq_id:
                        issue_data = {
                            "id": t.id,
                            "name": t.name,
                            "state": t.get_state_name(),
                            "priority": t.priority,
                            "assignee": t.assignee_name,
                            "target_date": t.target_date,
                            "project_name": pident,
                        }
                        await redis_service.set_json(cache_key, {
                            "project_id": pid,
                            "project_ident": pident,
                            "issue": issue_data
                        }, ttl=CACHE_TTL)
                        return pid, pident, issue_data
        except Exception:
            continue

    return None


async def close_issue(project_id: str, issue_id: str) -> bool:
    """Close issue by setting state to 'completed' group."""
    states = await plane_api.get_project_states(project_id)
    done_state = None
    for s in states:
        if s.get('group') in ('completed',):
            done_state = s['id']
            break

    if not done_state:
        bot_logger.warning(f"No 'completed' state found for project {project_id}")
        return False

    result = await plane_api.update_issue(project_id, issue_id, state=done_state)
    return result is not None


async def assign_issue(project_id: str, issue_id: str, assignee_name: str) -> Optional[str]:
    """Assign issue to a member by fuzzy name match. Returns assigned name or None."""
    members = await plane_api.get_workspace_members()
    if not members:
        return None

    query = assignee_name.lower().strip()
    match = None
    for m in members:
        name = m.display_name if hasattr(m, 'display_name') else m.get('display_name', '')
        first = m.first_name if hasattr(m, 'first_name') else m.get('first_name', '')
        full = f"{first} {name}".lower()
        if query in full or query in name.lower():
            match = m
            break

    if not match:
        return None

    member_id = match.id if hasattr(match, 'id') else match.get('id')
    result = await plane_api.update_issue(project_id, issue_id, assignees=[member_id])
    display = match.display_name if hasattr(match, 'display_name') else match.get('display_name', '?')
    return display if result else None


async def add_comment(project_id: str, issue_id: str, comment_text: str) -> bool:
    """Add comment to an issue."""
    result = await plane_api.create_issue_comment(project_id, issue_id, comment_text)
    return result is not None


async def get_members_list() -> str:
    """List workspace members for context."""
    members = await plane_api.get_workspace_members()
    if not members:
        return ""
    names = []
    for m in members:
        name = m.display_name if hasattr(m, 'display_name') else m.get('display_name', '')
        if name and name != 'info':
            names.append(name)
    return ", ".join(names)
