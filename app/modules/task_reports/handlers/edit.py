"""
Task Reports Edit Handlers

Handlers for editing report fields and metadata
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from ..utils import parse_report_id_safely
from ....database.database import get_async_session
from ....services.task_reports_service import task_reports_service
from ....utils.logger import bot_logger
import json


router = Router(name="task_reports_edit")


# ═══════════════════════════════════════════════════════════
# CALLBACK: EDIT REPORT
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("edit_report:"))
async def callback_edit_report(callback: CallbackQuery, state: FSMContext):
    """
    Admin wants to edit report - show menu with all editable fields
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

            # Format current metadata for display
            duration_display = task_report.work_duration or "⚠️ Не указано"
            work_type_display = "Выезд" if task_report.is_travel else "Удалённо" if task_report.is_travel is not None else "⚠️ Не указано"
            company_display = task_report.company or "⚠️ Не указано"

            if task_report.workers:
                try:
                    workers_list = json.loads(task_report.workers)
                    workers_display = ", ".join(workers_list)
                except:
                    workers_display = task_report.workers
            else:
                workers_display = "⚠️ Не указано"

            report_preview = task_report.report_text[:100] + "..." if task_report.report_text and len(task_report.report_text) > 100 else task_report.report_text or "⚠️ Не заполнено"

            # Build edit menu
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"📝 Текст отчёта: {report_preview[:30]}...",
                    callback_data=f"edit_field:text:{task_report_id}"
                )],
                [InlineKeyboardButton(
                    text=f"⏱️ Длительность: {duration_display}",
                    callback_data=f"edit_field:duration:{task_report_id}"
                )],
                [InlineKeyboardButton(
                    text=f"🚗 Тип работы: {work_type_display}",
                    callback_data=f"edit_field:work_type:{task_report_id}"
                )],
                [InlineKeyboardButton(
                    text=f"🏢 Компания: {company_display[:30]}",
                    callback_data=f"edit_field:company:{task_report_id}"
                )],
                [InlineKeyboardButton(
                    text=f"👥 Исполнители: {workers_display[:30]}",
                    callback_data=f"edit_field:workers:{task_report_id}"
                )],
                [InlineKeyboardButton(
                    text="◀️ Назад к предпросмотру",
                    callback_data=f"preview_report:{task_report_id}"
                )],
                [InlineKeyboardButton(
                    text="❌ Отменить",
                    callback_data=f"cancel_report:{task_report_id}"
                )]
            ])

            await callback.message.edit_text(
                f"✏️ **Меню редактирования отчёта**\n\n"
                f"**Задача:** #{task_report.plane_sequence_id}\n\n"
                f"Выберите поле для редактирования:",
                parse_mode="Markdown",
                reply_markup=keyboard
            )

            await callback.answer()

    except Exception as e:
        bot_logger.error(f"❌ Error in edit_report callback: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)
