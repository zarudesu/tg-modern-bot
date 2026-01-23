"""
Task Reports AI Generation Handlers

Handlers for AI-powered report generation using OpenAI/Anthropic.
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery
import json

from ..utils import parse_report_id_safely, map_workers_to_display_names_async
from ..keyboards import create_final_review_keyboard
from ....database.database import get_async_session
from ....services.task_reports_service import task_reports_service
from ....services.ai_report_generator import ai_report_generator, ReportContext
from ....utils.logger import bot_logger


router = Router(name="task_reports_ai")


@router.callback_query(F.data.startswith("ai_generate:"))
async def callback_ai_generate(callback: CallbackQuery):
    """
    Generate AI summary for task report based on Plane data.

    Uses task title, description, and comments to create a professional
    client-facing report summary.
    """
    try:
        try:
            task_report_id = parse_report_id_safely(callback.data)
        except ValueError as e:
            bot_logger.error(f"Invalid report_id in AI generate callback: {e}")
            await callback.answer("Неверный ID отчёта", show_alert=True)
            return

        # Show loading state
        await callback.answer("Генерирую отчёт через AI...")
        await callback.message.edit_text(
            "🤖 <b>Генерация AI отчёта...</b>\n\n"
            "Анализирую данные задачи из Plane...",
            parse_mode="HTML"
        )

        async for session in get_async_session():
            task_report = await task_reports_service.get_task_report(session, task_report_id)

            if not task_report:
                await callback.message.edit_text(
                    "❌ Отчёт не найден",
                    parse_mode="HTML"
                )
                return

            # Build context for AI
            # Parse workers list
            workers_list = []
            if task_report.workers:
                try:
                    workers_list = json.loads(task_report.workers)
                except:
                    workers_list = [task_report.workers]

            # Map workers to display names
            workers_display = []
            if workers_list:
                display_str = await map_workers_to_display_names_async(session, workers_list)
                workers_display = display_str.split(", ")

            # Parse comments from Plane (if available in plane_data)
            comments = []
            if task_report.plane_data:
                try:
                    plane_data = json.loads(task_report.plane_data) if isinstance(task_report.plane_data, str) else task_report.plane_data
                    comments = plane_data.get("comments", [])
                except:
                    pass

            # Determine travel type
            travel_type = None
            if task_report.is_travel is not None:
                travel_type = "onsite" if task_report.is_travel else "remote"

            # Parse duration to minutes
            duration_minutes = None
            if task_report.work_duration:
                duration_minutes = _parse_duration_to_minutes(task_report.work_duration)

            context = ReportContext(
                task_title=task_report.task_title or "Без названия",
                task_description=task_report.task_description,
                comments=comments,
                company_name=task_report.company or "Не указана",
                workers=workers_display,
                duration_minutes=duration_minutes,
                travel_type=travel_type
            )

            # Generate AI summary
            result = await ai_report_generator.generate_summary(context, detailed=False)

            if not result.success:
                await callback.message.edit_text(
                    f"❌ <b>Ошибка AI генерации</b>\n\n"
                    f"{result.error}\n\n"
                    f"Попробуйте редактировать вручную.",
                    parse_mode="HTML",
                    reply_markup=create_final_review_keyboard(
                        task_report_id=task_report_id,
                        has_client=bool(task_report.client_chat_id),
                        has_request_chat=bool(task_report.support_request_id and task_report.client_chat_id)
                    )
                )
                return

            # Update report with AI-generated text
            task_report.report_text = result.summary
            await session.commit()

            bot_logger.info(
                f"AI generated report for task #{task_report.plane_sequence_id}: "
                f"{len(result.summary)} chars"
            )

            # Show updated preview
            preview = result.summary.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

            # Format metadata (same as preview.py)
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

            if workers_display:
                workers_str = ", ".join(workers_display)
                workers_escaped = workers_str.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                metadata_text += f"👥 Исполнители: <b>{workers_escaped}</b>\n"
            else:
                metadata_text += "👥 Исполнители: ⚠️ <i>Не указано</i>\n"

            has_client = bool(task_report.client_chat_id)
            has_request_chat = bool(task_report.support_request_id and task_report.client_chat_id)

            await callback.message.edit_text(
                f"🤖 <b>AI отчёт сгенерирован!</b>\n\n"
                f"<b>Задача:</b> #{task_report.plane_sequence_id}\n"
                f"<b>Клиент:</b> {'✅ Есть' if has_client else '⚠️ Нет привязки'}\n\n"
                f"{metadata_text}\n"
                f"<b>ОТЧЁТ ДЛЯ КЛИЕНТА (AI):</b>\n{preview}\n\n"
                f"<i>Проверьте текст и отправьте клиенту</i>",
                parse_mode="HTML",
                reply_markup=create_final_review_keyboard(
                    task_report_id=task_report_id,
                    has_client=has_client,
                    has_request_chat=has_request_chat
                )
            )

    except Exception as e:
        bot_logger.error(f"Error in AI generate callback: {e}")
        await callback.message.edit_text(
            f"❌ <b>Ошибка генерации</b>\n\n{str(e)}",
            parse_mode="HTML"
        )


def _parse_duration_to_minutes(duration_str: str) -> int:
    """Parse duration string to minutes (e.g., '1.5 часа' -> 90)"""
    try:
        duration_str = duration_str.lower().strip()

        # Handle hour formats
        if 'час' in duration_str:
            # Extract number (handle both "1 час" and "1.5 часа")
            num_str = duration_str.split()[0].replace(',', '.')
            hours = float(num_str)
            return int(hours * 60)

        # Handle minute formats
        if 'мин' in duration_str:
            num_str = duration_str.split()[0]
            return int(num_str)

        # Try to parse as number (assume minutes)
        return int(float(duration_str))

    except:
        return 0
