"""
AI Training Data Export — /ai_export command.

Exports DetectedIssue records as JSONL for LLM fine-tuning.
"""

import json
import tempfile
from datetime import datetime, timedelta, timezone

from aiogram import Router
from aiogram.types import Message, BufferedInputFile
from aiogram.filters import Command
from sqlalchemy import select

from ..config import settings
from ..utils.logger import bot_logger
from ..database.chat_ai_models import DetectedIssue
from ..database.database import AsyncSessionLocal

router = Router(name="ai_training_export")


@router.message(Command("ai_export"))
async def cmd_ai_export(message: Message):
    """
    /ai_export [days] — Export AI detection data as JSONL.
    Admin-only. Default: last 30 days.
    """
    if not settings.is_admin(message.from_user.id):
        await message.answer("❌ Команда доступна только администраторам")
        return

    args = message.text.split(maxsplit=1)
    days = 30
    if len(args) > 1:
        try:
            days = int(args[1].strip())
        except ValueError:
            await message.answer("❌ Укажите число дней: /ai_export 30")
            return

    status_msg = await message.answer(f"⏳ Экспортирую данные за {days} дней...")

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(DetectedIssue)
                .where(DetectedIssue.created_at >= cutoff)
                .order_by(DetectedIssue.created_at)
            )
            issues = result.scalars().all()

        if not issues:
            await status_msg.edit_text(f"📋 Нет данных за последние {days} дней")
            return

        # Build JSONL
        lines = []
        stats = {"total": 0, "accepted": 0, "rejected": 0, "corrected": 0, "no_feedback": 0}

        for issue in issues:
            stats["total"] += 1
            fb = issue.user_feedback or "no_feedback"
            stats[fb] = stats.get(fb, 0) + 1

            record = {
                "prompt": {
                    "original_text": issue.original_text,
                    "chat_id": issue.chat_id,
                },
                "completion": {
                    "is_task": True,
                    "title": issue.title,
                    "description": issue.description,
                    "confidence": issue.confidence,
                },
                "metadata": {
                    "id": issue.id,
                    "issue_type": issue.issue_type,
                    "ai_model": issue.ai_model_used,
                    "user_feedback": issue.user_feedback,
                    "user_edited_title": issue.user_edited_title,
                    "user_edited_desc": issue.user_edited_desc,
                    "user_assigned_to": issue.user_assigned_to,
                    "correction_distance": issue.correction_distance,
                    "plane_issue_id": issue.plane_issue_id,
                    "created_at": issue.created_at.isoformat() if issue.created_at else None,
                    "feedback_at": issue.feedback_at.isoformat() if issue.feedback_at else None,
                },
            }

            # Include raw AI response if available
            if issue.ai_response_json:
                try:
                    record["ai_raw"] = json.loads(issue.ai_response_json)
                except (json.JSONDecodeError, TypeError):
                    record["ai_raw"] = issue.ai_response_json

            lines.append(json.dumps(record, ensure_ascii=False, default=str))

        content = "\n".join(lines)
        filename = f"ai_training_data_{days}d_{datetime.now().strftime('%Y%m%d')}.jsonl"

        await message.answer_document(
            BufferedInputFile(content.encode("utf-8"), filename=filename),
            caption=(
                f"📊 <b>AI Training Export</b>\n\n"
                f"📋 Записей: {stats['total']}\n"
                f"✅ Accepted: {stats.get('accepted', 0)}\n"
                f"❌ Rejected: {stats.get('rejected', 0)}\n"
                f"✏️ Corrected: {stats.get('corrected', 0)}\n"
                f"⏳ No feedback: {stats.get('no_feedback', 0)}\n\n"
                f"📅 Период: {days} дней"
            ),
            parse_mode="HTML"
        )

        await status_msg.delete()
        bot_logger.info(f"AI training data exported: {stats['total']} records, {days} days")

    except Exception as e:
        bot_logger.error(f"Error in ai_export: {e}")
        import traceback
        bot_logger.error(traceback.format_exc())
        await status_msg.edit_text(f"❌ <b>Ошибка:</b> {e}", parse_mode="HTML")
