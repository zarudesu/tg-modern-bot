"""
Plane Audit handler — /plane_audit command.

Deep analysis of all Plane issues: overdue, stale, unassigned, workload,
recently completed, and AI-powered recommendations.
"""

from datetime import datetime, timedelta, timezone
from collections import defaultdict

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from ..config import settings
from ..utils.logger import bot_logger
from ..integrations.plane import plane_api
from ..core.ai.ai_manager import ai_manager

router = Router(name="plane_audit")


@router.message(Command("plane_audit"))
async def cmd_plane_audit(message: Message):
    """
    /plane_audit [project] — Deep AI audit of Plane issues.
    Admin-only.
    """
    if not settings.is_admin(message.from_user.id):
        await message.answer("❌ Команда доступна только администраторам")
        return

    if not plane_api.configured:
        await message.answer("❌ Plane API не настроен")
        return

    args = message.text.split(maxsplit=1)
    filter_project = args[1].strip().upper() if len(args) > 1 else None

    status_msg = await message.answer("⏳ <b>Полный аудит Plane...</b>", parse_mode="HTML")

    try:
        projects = await plane_api.get_all_projects()
        if not projects:
            await status_msg.edit_text("❌ Нет проектов", parse_mode="HTML")
            return

        if filter_project:
            projects = [
                p for p in projects
                if filter_project in (p.get('name', '').upper(), p.get('identifier', '').upper())
            ]
            if not projects:
                await status_msg.edit_text(
                    f"❌ Проект <b>{filter_project}</b> не найден", parse_mode="HTML"
                )
                return

        now = datetime.now(timezone.utc)
        stale_7d = now - timedelta(days=7)
        stale_14d = now - timedelta(days=14)

        # Collect data across all projects
        critical = []       # overdue + stale >14d in progress
        attention = []      # stale >7d, no deadline, unassigned
        workload = defaultdict(lambda: {"urgent": 0, "high": 0, "medium": 0, "low": 0, "none": 0, "total": 0})
        archive_candidates = []  # Done >30d
        recently_done = []
        all_open = []
        project_stats = []

        for proj in projects:
            pid = proj['id']
            pname = proj.get('identifier') or proj.get('name', '?')

            tasks = await plane_api.get_all_issues_for_audit(pid, include_done_since_days=30)
            if not tasks:
                continue

            open_tasks = []
            done_tasks = []
            for t in tasks:
                sn = (t.state_name or '').lower()
                if sn in ('done', 'completed', 'cancelled', 'canceled'):
                    done_tasks.append(t)
                else:
                    open_tasks.append(t)

            project_stats.append(f"📂 <b>{pname}</b>: {len(open_tasks)} открытых, {len(done_tasks)} завершённых")

            for t in open_tasks:
                all_open.append((pname, t))
                prio = t.priority or 'none'
                assignee = t.assignee_name or 'Unassigned'

                # Workload
                if assignee != 'Unassigned':
                    for a_name in assignee.split(', '):
                        workload[a_name][prio] += 1
                        workload[a_name]["total"] += 1

                updated_dt = None
                if t.updated_at:
                    try:
                        updated_dt = datetime.fromisoformat(t.updated_at.replace('Z', '+00:00'))
                    except (ValueError, TypeError):
                        pass

                is_in_progress = 'progress' in (t.state_name or '').lower() or 'started' in (t.state_name or '').lower()
                is_stale_14 = updated_dt and updated_dt < stale_14d
                is_stale_7 = updated_dt and updated_dt < stale_7d

                # Critical: overdue OR stale >14d in progress
                if t.is_overdue or (is_in_progress and is_stale_14):
                    reason = "просрочена" if t.is_overdue else "застряла >14д"
                    critical.append(f"🔴 #{t.sequence_id} {t.name[:40]} [{pname}] — {reason} ({assignee})")

                # Attention: stale >7d, no deadline, unassigned
                elif is_stale_7 or (assignee == 'Unassigned') or (not t.target_date and prio in ('urgent', 'high')):
                    reasons = []
                    if is_stale_7:
                        reasons.append("без движения >7д")
                    if assignee == 'Unassigned':
                        reasons.append("нет исполнителя")
                    if not t.target_date and prio in ('urgent', 'high'):
                        reasons.append("нет дедлайна")
                    attention.append(f"🟡 #{t.sequence_id} {t.name[:40]} [{pname}] — {', '.join(reasons)}")

            # Archive candidates: done > 30 days ago (already filtered by audit method)
            for t in done_tasks:
                recently_done.append(f"✅ #{t.sequence_id} {t.name[:35]} [{pname}]")

        if not all_open and not recently_done:
            await status_msg.edit_text("📋 Нет задач для аудита", parse_mode="HTML")
            return

        # Build report
        parts = [f"📊 <b>Plane Audit Report</b>\n"]
        parts.append("\n".join(project_stats))

        total_open = len(all_open)
        parts.append(f"\n📋 Всего открытых: <b>{total_open}</b>")

        if critical:
            parts.append(f"\n\n🚨 <b>КРИТИЧНО ({len(critical)})</b>")
            parts.extend(critical[:10])
            if len(critical) > 10:
                parts.append(f"<i>...и ещё {len(critical) - 10}</i>")

        if attention:
            parts.append(f"\n\n⚠️ <b>ВНИМАНИЕ ({len(attention)})</b>")
            parts.extend(attention[:10])
            if len(attention) > 10:
                parts.append(f"<i>...и ещё {len(attention) - 10}</i>")

        if workload:
            parts.append(f"\n\n👥 <b>НАГРУЗКА</b>")
            for name, stats in sorted(workload.items(), key=lambda x: -x[1]["total"]):
                urgent_high = stats["urgent"] + stats["high"]
                flag = " ⚠️" if urgent_high >= 3 else ""
                parts.append(
                    f"  {name}: {stats['total']} задач "
                    f"(🔴{stats['urgent']} 🟠{stats['high']} 🟡{stats['medium']} 🟢{stats['low']}){flag}"
                )

        if recently_done:
            parts.append(f"\n\n✅ <b>ЗАВЕРШЕНО (последние 30д): {len(recently_done)}</b>")
            for line in recently_done[:5]:
                parts.append(f"  {line}")
            if len(recently_done) > 5:
                parts.append(f"  <i>...и ещё {len(recently_done) - 5}</i>")

        report_text = "\n".join(parts)

        # Truncate if too long for Telegram
        if len(report_text) > 3800:
            report_text = report_text[:3800] + "\n\n<i>...отчёт обрезан</i>"

        await status_msg.edit_text(report_text, parse_mode="HTML")

        # AI analysis
        if ai_manager.providers_count > 0 and total_open > 0:
            try:
                ai_prompt = (
                    f"Вот полный аудит задач в Plane:\n\n{report_text}\n\n"
                    f"Проанализируй и дай рекомендации (на русском, 5-7 предложений):\n"
                    f"1. Какие задачи критически застряли и требуют немедленного внимания?\n"
                    f"2. Есть ли перегруженные исполнители? Кому стоит перераспределить?\n"
                    f"3. Задачи без исполнителя или дедлайна — что делать?\n"
                    f"4. Общие рекомендации по приоритизации и оптимизации.\n"
                    f"5. Что можно отправить в архив?"
                )
                ai_response = await ai_manager.chat(
                    user_message=ai_prompt,
                    system_prompt=(
                        "Ты — опытный IT менеджер проектов. Анализируй задачи кратко и конкретно. "
                        "Давай actionable рекомендации. Не повторяй данные — давай выводы."
                    )
                )
                if ai_response and ai_response.content:
                    ai_text = f"🤖 <b>AI Рекомендации:</b>\n\n{ai_response.content}"
                    if len(ai_text) > 4000:
                        ai_text = ai_text[:4000] + "..."
                    await message.answer(ai_text, parse_mode="HTML")
            except Exception as e:
                bot_logger.warning(f"AI audit analysis failed: {e}")

    except Exception as e:
        bot_logger.error(f"Error in plane_audit: {e}")
        import traceback
        bot_logger.error(traceback.format_exc())
        await status_msg.edit_text(f"❌ <b>Ошибка:</b> {e}", parse_mode="HTML")


async def generate_audit_report_text(filter_project: str = None) -> str:
    """Generate audit report text for scheduled jobs (no Telegram message context)."""
    projects = await plane_api.get_all_projects()
    if not projects:
        return ""

    if filter_project:
        projects = [
            p for p in projects
            if filter_project in (p.get('name', '').upper(), p.get('identifier', '').upper())
        ]

    now = datetime.now(timezone.utc)
    stale_7d = now - timedelta(days=7)
    stale_14d = now - timedelta(days=14)

    critical_count = 0
    attention_count = 0
    total_open = 0
    report_parts = []

    for proj in projects:
        pid = proj['id']
        pname = proj.get('identifier') or proj.get('name', '?')
        tasks = await plane_api.get_all_issues_for_audit(pid, include_done_since_days=7)
        if not tasks:
            continue

        open_tasks = [t for t in tasks if (t.state_name or '').lower() not in ('done', 'completed', 'cancelled', 'canceled')]
        total_open += len(open_tasks)

        stale = 0
        overdue = 0
        unassigned = 0
        for t in open_tasks:
            if t.is_overdue:
                overdue += 1
            if (t.assignee_name or 'Unassigned') == 'Unassigned':
                unassigned += 1
            if t.updated_at:
                try:
                    updated = datetime.fromisoformat(t.updated_at.replace('Z', '+00:00'))
                    if updated < stale_7d:
                        stale += 1
                except (ValueError, TypeError):
                    pass

        critical_count += overdue
        attention_count += stale + unassigned

        line = f"📂 {pname}: {len(open_tasks)} открытых"
        if overdue:
            line += f", 🔴 {overdue} просрочено"
        if stale:
            line += f", ⚠️ {stale} застряли"
        if unassigned:
            line += f", ❓ {unassigned} без исполнителя"
        report_parts.append(line)

    if not report_parts:
        return ""

    header = (
        f"📊 <b>Еженедельный аудит Plane</b>\n"
        f"📋 Всего открытых: {total_open}\n"
        f"🔴 Критично: {critical_count}\n"
        f"⚠️ Требуют внимания: {attention_count}\n\n"
    )

    return header + "\n".join(report_parts)
