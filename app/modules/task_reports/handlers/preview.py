"""
Task Reports Preview Handlers

Handlers for previewing completed reports before sending
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from ..utils import parse_report_id_safely
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
            preview = task_report.report_text[:2000] if task_report.report_text else "⚠️ Отчёт не заполнен"
            if task_report.report_text and len(task_report.report_text) > 2000:
                preview += "\n\n[...]"

            has_client = bool(task_report.client_chat_id)

            # Format metadata
            metadata_text = "\n**МЕТАДАННЫЕ РАБОТЫ:**\n"

            if task_report.work_duration:
                metadata_text += f"⏱️ Длительность: **{task_report.work_duration}**\n"
            else:
                metadata_text += "⏱️ Длительность: ⚠️ _Не указано_\n"

            if task_report.is_travel is not None:
                metadata_text += f"🚗 Тип работы: **{'Выезд' if task_report.is_travel else 'Удалённо'}**\n"
            else:
                metadata_text += "🚗 Тип работы: ⚠️ _Не указано_\n"

            if task_report.company:
                metadata_text += f"🏢 Компания: **{task_report.company}**\n"
            else:
                metadata_text += "🏢 Компания: ⚠️ _Не указано_\n"

            if task_report.workers:
                try:
                    workers_list = json.loads(task_report.workers)
                    workers_display = ", ".join(workers_list)
                except:
                    workers_display = task_report.workers
                metadata_text += f"👥 Исполнители: **{workers_display}**\n"
            else:
                metadata_text += "👥 Исполнители: ⚠️ _Не указано_\n"

            # Build keyboard based on client availability
            keyboard_buttons = []
            if has_client:
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text="✅ Одобрить и отправить",
                        callback_data=f"approve_send:{task_report_id}"
                    )
                ])
            else:
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text="✅ Одобрить (без отправки)",
                        callback_data=f"approve_only:{task_report_id}"
                    )
                ])

            keyboard_buttons.extend([
                [InlineKeyboardButton(
                    text="✏️ Редактировать",
                    callback_data=f"edit_report:{task_report_id}"
                )],
                [InlineKeyboardButton(
                    text="❌ Отменить",
                    callback_data=f"cancel_report:{task_report_id}"
                )]
            ])

            await callback.message.edit_text(
                f"👁️ **Предпросмотр отчёта**\n\n"
                f"**Задача:** #{task_report.plane_sequence_id}\n"
                f"**Клиент:** {'✅ Есть' if has_client else '⚠️ Нет привязки'}\n\n"
                f"{metadata_text}\n"
                f"**ОТЧЁТ ДЛЯ КЛИЕНТА:**\n{preview}\n\n"
                f"_Клиенту будет отправлен ТОЛЬКО текст отчёта (без метаданных)_",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            )

            await callback.answer()

    except Exception as e:
        bot_logger.error(f"❌ Error in preview_report callback: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)
