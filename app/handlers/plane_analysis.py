"""
Plane Analysis handler — /plane_status command.

Fetches open issues via Plane API, groups by state,
highlights stale tasks, and generates AI summary.
"""

from datetime import datetime, timedelta, timezone

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from ..config import settings
from ..utils.logger import bot_logger
from ..integrations.plane import plane_api
from ..core.ai.ai_manager import ai_manager

router = Router(name="plane_analysis")


@router.message(Command("plane_status"))
async def cmd_plane_status(message: Message):
    """
    /plane_status [project_name] — AI analysis of open Plane issues.
    Admin-only command.
    """
    if not settings.is_admin(message.from_user.id):
        await message.answer("❌ Команда доступна только администраторам")
        return

    if not plane_api.configured:
        await message.answer("❌ Plane API не настроен")
        return

    # Parse project name from arguments
    args = message.text.split(maxsplit=1)
    filter_project = args[1].strip().upper() if len(args) > 1 else None

    status_msg = await message.answer("⏳ <b>Загружаю данные из Plane...</b>", parse_mode="HTML")

    try:
        projects = await plane_api.get_all_projects()
        if not projects:
            await status_msg.edit_text("❌ Не удалось получить проекты", parse_mode="HTML")
            return

        if filter_project:
            projects = [p for p in projects if filter_project in (p.get('name', '').upper(), p.get('identifier', '').upper())]
            if not projects:
                await status_msg.edit_text(
                    f"❌ Проект <b>{filter_project}</b> не найден",
                    parse_mode="HTML"
                )
                return

        all_report_lines = []
        total_open = 0
        total_stale = 0
        now = datetime.now(timezone.utc)
        stale_threshold = now - timedelta(days=7)

        for proj in projects:
            pid = proj['id']
            pname = proj.get('identifier') or proj.get('name', '?')

            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    tasks = await plane_api._tasks_manager._get_project_issues(
                        session, pid, assigned_only=False
                    )
            except Exception as e:
                bot_logger.warning(f"Failed to fetch issues for {pname}: {e}")
                continue

            if not tasks:
                continue

            # Group by state
            groups = {}
            stale_tasks = []
            for t in tasks:
                state = t.state_name or "Unknown"
                groups.setdefault(state, []).append(t)

                # Check staleness
                if t.updated_at:
                    try:
                        updated = datetime.fromisoformat(t.updated_at.replace('Z', '+00:00'))
                        if updated < stale_threshold:
                            stale_tasks.append(t)
                    except (ValueError, TypeError):
                        pass

            total_open += len(tasks)
            total_stale += len(stale_tasks)

            lines = [f"\n<b>📂 {pname}</b> ({len(tasks)} открытых)"]
            for state, items in sorted(groups.items()):
                lines.append(f"  <b>{state}:</b> {len(items)}")
                for t in items[:5]:  # Show max 5 per state
                    assignees = ", ".join(t.assignee_names) if t.assignee_names else "—"
                    lines.append(f"    • #{t.sequence_id} {t.name[:40]} [{assignees}]")
                if len(items) > 5:
                    lines.append(f"    <i>...и ещё {len(items) - 5}</i>")

            if stale_tasks:
                lines.append(f"\n  ⚠️ <b>Без обновлений &gt;7 дней:</b> {len(stale_tasks)}")
                for t in stale_tasks[:3]:
                    lines.append(f"    • #{t.sequence_id} {t.name[:40]}")

            all_report_lines.extend(lines)

        if not all_report_lines:
            await status_msg.edit_text("📋 Нет открытых задач", parse_mode="HTML")
            return

        # Build report text
        header = (
            f"📊 <b>Plane Status Report</b>\n"
            f"📋 Открытых задач: {total_open}\n"
            f"⚠️ Без движения &gt;7 дней: {total_stale}\n"
        )

        report_text = header + "\n".join(all_report_lines)

        # Truncate if too long for Telegram
        if len(report_text) > 3800:
            report_text = report_text[:3800] + "\n\n<i>...отчёт обрезан</i>"

        await status_msg.edit_text(report_text, parse_mode="HTML")

        # AI summary (if available)
        if ai_manager.providers_count > 0 and total_open > 0:
            try:
                summary_prompt = (
                    f"Вот отчёт по открытым задачам в проект-менеджере Plane.\n\n"
                    f"{report_text}\n\n"
                    f"Кратко проанализируй (на русском, 3-5 предложений):\n"
                    f"1. Какие задачи застряли и требуют внимания?\n"
                    f"2. Есть ли задачи без исполнителя?\n"
                    f"3. Общие рекомендации по приоритизации."
                )
                ai_response = await ai_manager.chat(
                    user_message=summary_prompt,
                    system_prompt="Ты помощник руководителя IT отдела. Анализируй задачи кратко и по делу."
                )
                if ai_response and ai_response.content:
                    await message.answer(
                        f"🤖 <b>AI Анализ:</b>\n\n{ai_response.content}",
                        parse_mode="HTML"
                    )
            except Exception as e:
                bot_logger.warning(f"AI analysis failed: {e}")

    except Exception as e:
        bot_logger.error(f"Error in plane_status: {e}")
        await status_msg.edit_text(
            f"❌ <b>Ошибка:</b> {e}",
            parse_mode="HTML"
        )
