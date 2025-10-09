"""
Task Reports Creation Handlers

Handlers for starting and managing the report creation flow
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from ..states import TaskReportStates
from ..utils import parse_report_id_safely
from ....database.database import get_async_session
from ....services.task_reports_service import task_reports_service
from ....utils.logger import bot_logger
from ....utils.keyboards import get_back_to_main_menu_keyboard


router = Router(name="task_reports_creation")


# ═══════════════════════════════════════════════════════════
# CALLBACK: START FILLING REPORT
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("fill_report:"))
async def callback_fill_report(callback: CallbackQuery, state: FSMContext):
    """
    Admin clicks "Fill Report" button from notification

    Callback data format: fill_report:{task_report_id}

    НОВОЕ: Загружаем Plane данные (project, assignees) в FSM state для автоподстановки
    """
    try:
        try:
            task_report_id = parse_report_id_safely(callback.data)
        except ValueError as e:
            bot_logger.error(f"Invalid report_id in callback: {e}")
            await callback.answer("❌ Неверный ID отчёта", show_alert=True)
            return
        bot_logger.info(f"📝 Admin {callback.from_user.id} started filling report #{task_report_id}")

        # Get task report from DB
        async for session in get_async_session():
            task_report = await task_reports_service.get_task_report(session, task_report_id)

            if not task_report:
                await callback.answer("❌ Отчёт не найден", show_alert=True)
                return

            # ═════════════════════════════════════════════════════════
            # НОВОЕ: Загрузка Plane данных для автоподстановки
            # ═════════════════════════════════════════════════════════
            from ....integrations.plane import plane_api

            plane_project_name = None
            plane_assignees = []

            if plane_api.configured and task_report.plane_project_id and task_report.plane_issue_id:
                try:
                    bot_logger.info(f"📥 Loading Plane data for task #{task_report.plane_sequence_id}...")

                    # Fetch issue details (assignees, priority)
                    plane_details = await plane_api.get_issue_details(
                        project_id=task_report.plane_project_id,
                        issue_id=task_report.plane_issue_id
                    )

                    # Get project name
                    projects = await plane_api.get_all_projects()
                    project_match = next((p for p in projects if p['id'] == task_report.plane_project_id), None)
                    if project_match:
                        plane_project_name = project_match['name']

                    # Get assignees
                    if plane_details and plane_details.get('assignee_details'):
                        plane_assignees = [
                            assignee.get('display_name') or assignee.get('first_name', 'Unknown')
                            for assignee in plane_details['assignee_details']
                        ]

                    # Add "who closed" if not in assignees
                    if task_report.closed_by_plane_name and task_report.closed_by_plane_name not in plane_assignees:
                        plane_assignees.append(task_report.closed_by_plane_name)

                    bot_logger.info(
                        f"✅ Loaded Plane data: project={plane_project_name}, "
                        f"assignees={plane_assignees}"
                    )

                except Exception as e:
                    bot_logger.warning(f"⚠️ Failed to load Plane data: {e}")

            # Set FSM state with Plane data
            await state.set_state(TaskReportStates.filling_report)
            await state.update_data(
                task_report_id=task_report_id,
                # Plane данные для автоподстановки
                plane_project_name=plane_project_name,
                plane_assignees=plane_assignees,
                plane_closed_by=task_report.closed_by_plane_name
            )

            bot_logger.info(
                f"💾 Saved to FSM state: project={plane_project_name}, "
                f"assignees={plane_assignees}, closed_by={task_report.closed_by_plane_name}"
            )

            # Show autofilled text if available
            if task_report.report_text:
                preview_text = task_report.report_text[:500]
                if len(task_report.report_text) > 500:
                    preview_text += "..."

                # Escape HTML
                preview_escaped = preview_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

                autofill_notice = ""
                if task_report.auto_filled_from_journal:
                    autofill_notice = "\n\n✅ <i>Автоматически заполнено из work journal</i>"

                await callback.message.edit_text(
                    f"📝 <b>Заполнение отчёта для задачи #{task_report.plane_sequence_id}</b>\n\n"
                    f"<b>Текущий текст отчёта:</b>\n{preview_escaped}{autofill_notice}\n\n"
                    f"Отправьте новый текст отчёта или согласуйте текущий:",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(
                            text="✅ Согласовать текст и продолжить",
                            callback_data=f"agree_text:{task_report_id}"
                        )],
                        [InlineKeyboardButton(
                            text="❌ Отменить",
                            callback_data=f"cancel_report:{task_report_id}"
                        )]
                    ])
                )
            else:
                # НОВЫЙ ФЛОУ: Сразу показываем кнопки выбора длительности (метаданные)
                from ..keyboards import create_duration_keyboard

                # Escape task title
                title_escaped = task_report.task_title.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

                await callback.message.edit_text(
                    f"📝 <b>Заполнение отчёта для задачи #{task_report.plane_sequence_id}</b>\n\n"
                    f"<b>Название задачи:</b> {title_escaped}\n\n"
                    f"⏱️ <b>Шаг 1/4:</b> Выберите длительность работы:",
                    parse_mode="HTML",
                    reply_markup=create_duration_keyboard(task_report_id)
                )

            await callback.answer()

    except Exception as e:
        bot_logger.error(f"❌ Error in fill_report callback: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


# ═══════════════════════════════════════════════════════════
# TEXT HANDLER: RECEIVE REPORT TEXT
# ═══════════════════════════════════════════════════════════

@router.message(StateFilter(TaskReportStates.filling_report), F.text)
async def handle_report_text(message: Message, state: FSMContext):
    """
    Admin sends report text while in filling_report state
    """
    try:
        user_id = message.from_user.id
        report_text = message.text.strip()

        bot_logger.info(f"📨 Received report text from admin {user_id}")

        # Get state data
        state_data = await state.get_data()
        task_report_id = state_data.get("task_report_id")

        if not task_report_id:
            await message.reply("❌ Ошибка: не найден ID отчёта")
            await state.clear()
            return

        # Validate length
        if len(report_text) < 10:
            await message.reply(
                "❌ Отчёт слишком короткий (минимум 10 символов).\n\n"
                "Пожалуйста, опишите выполненную работу подробнее."
            )
            return

        # Save report text
        async for session in get_async_session():
            task_report = await task_reports_service.update_report_text(
                session=session,
                task_report_id=task_report_id,
                report_text=report_text,
                submitted_by_telegram_id=user_id
            )

            if not task_report:
                await message.reply("❌ Ошибка сохранения отчёта")
                await state.clear()
                return

            # Move to duration collection state
            await state.set_state(TaskReportStates.filling_duration)

            # Start metadata collection with duration keyboard
            from ..keyboards import create_duration_keyboard
            keyboard = create_duration_keyboard(task_report_id)

            await message.reply(
                f"✅ <b>Текст отчёта сохранён!</b>\n\n"
                f"⏱️ <b>Укажите длительность работы</b>\n\n"
                f"Выберите из предложенных вариантов или укажите своё время:",
                parse_mode="HTML",
                reply_markup=keyboard
            )

    except Exception as e:
        bot_logger.error(f"❌ Error handling report text: {e}")
        await message.reply("❌ Произошла ошибка при сохранении отчёта")
        await state.clear()


# ═══════════════════════════════════════════════════════════
# CALLBACK: CANCEL REPORT
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("cancel_report:"))
async def callback_cancel_report(callback: CallbackQuery, state: FSMContext):
    """
    Admin cancels report filling
    """
    try:
        try:
            task_report_id = parse_report_id_safely(callback.data)
        except ValueError as e:
            bot_logger.error(f"Invalid report_id in callback: {e}")
            await callback.answer("❌ Неверный ID отчёта", show_alert=True)
            return

        bot_logger.info(f"❌ Admin {callback.from_user.id} cancelled report #{task_report_id}")

        await callback.message.edit_text(
            "❌ Заполнение отчёта отменено.\n\n"
            "Напоминание будет отправлено позже.",
            reply_markup=get_back_to_main_menu_keyboard()
        )

        # Clear FSM state
        await state.clear()

        await callback.answer()

    except Exception as e:
        bot_logger.error(f"❌ Error in cancel_report callback: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)
