"""
Task Reports Preview Handlers

Handlers for previewing completed reports before sending
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from ..utils import parse_report_id_safely, map_workers_to_display_names
from ..keyboards import create_final_review_keyboard
from ....database.database import get_async_session
from ....services.task_reports_service import task_reports_service
from ....utils.logger import bot_logger
import json


router = Router(name="task_reports_preview")


# ═══════════════════════════════════════════════════════════
# CALLBACK: PREVIEW REPORT
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("preview_report:"))
async def callback_preview_report(callback: CallbackQuery):
    """
    Show preview of auto-generated report
    """
    try:
        try:
            task_report_id = parse_report_id_safely(callback.data)
        except ValueError as e:
            bot_logger.error(f"Invalid report_id in callback: {e}")
            await callback.answer("❌ Неверный ID отчёта", show_alert=True)
            return

        async for session in get_async_session():
            task_report = await task_reports_service.get_task_report(session, task_report_id)

            if not task_report:
                await callback.answer("❌ Отчёт не найден", show_alert=True)
                return

            if not task_report.report_text:
                await callback.answer("❌ Отчёт пока не заполнен", show_alert=True)
                return

            # Show report preview with metadata
            # Escape HTML characters in report text
            preview_text = task_report.report_text[:2000] if task_report.report_text else "⚠️ Отчёт не заполнен"
            if task_report.report_text and len(task_report.report_text) > 2000:
                preview_text += "\n\n[...]"

            # Escape HTML special chars
            preview = preview_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

            has_client = bool(task_report.client_chat_id)
            has_request_chat = bool(task_report.support_request_id and task_report.client_chat_id)

            # Format metadata (HTML)
            metadata_text = "\n<b>МЕТАДАННЫЕ РАБОТЫ:</b>\n"

            if task_report.work_duration:
                duration_escaped = task_report.work_duration.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                metadata_text += f"⏱️ Длительность: <b>{duration_escaped}</b>\n"
            else:
                metadata_text += "⏱️ Длительность: ⚠️ <i>Не указано</i>\n"

            if task_report.is_travel is not None:
                metadata_text += f"🚗 Тип работы: <b>{'Выезд' if task_report.is_travel else 'Удалённо'}</b>\n"
            else:
                metadata_text += "🚗 Тип работы: ⚠️ <i>Не указано</i>\n"

            if task_report.company:
                company_escaped = task_report.company.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                metadata_text += f"🏢 Компания: <b>{company_escaped}</b>\n"
            else:
                metadata_text += "🏢 Компания: ⚠️ <i>Не указано</i>\n"

            if task_report.workers:
                try:
                    workers_list = json.loads(task_report.workers)
                    # Map telegram usernames to display names (zardes → Костя)
                    workers_display = map_workers_to_display_names(workers_list)
                except:
                    workers_display = task_report.workers
                workers_escaped = workers_display.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                metadata_text += f"👥 Исполнители: <b>{workers_escaped}</b>\n"
            else:
                metadata_text += "👥 Исполнители: ⚠️ <i>Не указано</i>\n"

            # Build keyboard using shared function
            keyboard = create_final_review_keyboard(
                task_report_id=task_report_id,
                has_client=has_client,
                has_request_chat=has_request_chat
            )

            await callback.message.edit_text(
                f"👁️ <b>Предпросмотр отчёта</b>\n\n"
                f"<b>Задача:</b> #{task_report.plane_sequence_id}\n"
                f"<b>Клиент:</b> {'✅ Есть' if has_client else '⚠️ Нет привязки'}\n\n"
                f"{metadata_text}\n"
                f"<b>ОТЧЁТ ДЛЯ КЛИЕНТА:</b>\n{preview}\n\n"
                f"<i>Клиенту будет отправлен ТОЛЬКО текст отчёта (без метаданных)</i>",
                parse_mode="HTML",
                reply_markup=keyboard
            )

            await callback.answer()

    except Exception as e:
        bot_logger.error(f"❌ Error in preview_report callback: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)
