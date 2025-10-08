"""
Task Reports Metadata - Navigation and Edit Handlers

Back buttons and field editing handlers
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
import json

from ..states import TaskReportStates
from ..keyboards import (
    create_duration_keyboard,
    create_work_type_keyboard,
    create_company_keyboard,
    create_workers_keyboard
)
from ..utils import parse_report_id_safely
from ....database.database import get_async_session
from ....services.task_reports_service import task_reports_service
from ....services import work_journal_service
from ....utils.logger import bot_logger


router = Router(name="task_reports_navigation")


# ═══════════════════════════════════════════════════════════
# NAVIGATION (BACK BUTTONS)
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("tr_back_to_duration:"))
async def callback_back_to_duration(callback: CallbackQuery, state: FSMContext):
    """
    Navigate back to duration selection

    Callback format: tr_back_to_duration:{task_report_id}
    """
    try:
        try:
            task_report_id = parse_report_id_safely(callback.data)
        except ValueError as e:
            bot_logger.error(f"Invalid report_id in callback: {e}")
            await callback.answer("❌ Неверный ID отчёта", show_alert=True)
            return

        # Move state back
        await state.set_state(TaskReportStates.filling_duration)

        # Show duration keyboard
        keyboard = create_duration_keyboard(task_report_id)

        await callback.message.edit_text(
            "⏱️ **Укажите длительность работы**\n\n"
            "Выберите из предложенных вариантов или укажите своё время:",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

        await callback.answer()

    except Exception as e:
        bot_logger.error(f"❌ Error in back_to_duration callback: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("tr_back_to_work_type:"))
async def callback_back_to_work_type(callback: CallbackQuery, state: FSMContext):
    """
    Navigate back to work type selection

    Callback format: tr_back_to_work_type:{task_report_id}
    """
    try:
        try:
            task_report_id = parse_report_id_safely(callback.data)
        except ValueError as e:
            bot_logger.error(f"Invalid report_id in callback: {e}")
            await callback.answer("❌ Неверный ID отчёта", show_alert=True)
            return

        # Move state back
        await state.set_state(TaskReportStates.filling_work_type)

        # Show work type keyboard
        keyboard = create_work_type_keyboard(task_report_id)

        await callback.message.edit_text(
            "🚗 **Был ли выезд к клиенту?**",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

        await callback.answer()

    except Exception as e:
        bot_logger.error(f"❌ Error in back_to_work_type callback: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("tr_back_to_company:"))
async def callback_back_to_company(callback: CallbackQuery, state: FSMContext):
    """
    Navigate back to company selection

    Callback format: tr_back_to_company:{task_report_id}
    """
    try:
        try:
            task_report_id = parse_report_id_safely(callback.data)
        except ValueError as e:
            bot_logger.error(f"Invalid report_id in callback: {e}")
            await callback.answer("❌ Неверный ID отчёта", show_alert=True)
            return

        # Move state back
        await state.set_state(TaskReportStates.filling_company)

        # Get companies from work_journal
        async for session in get_async_session():
            wj_service = work_journal_service.WorkJournalService(session)
            companies = await wj_service.get_companies()

        # Get Plane company from FSM state
        state_data = await state.get_data()
        plane_company = state_data.get("plane_project_name")

        # Show company keyboard
        keyboard = create_company_keyboard(
            companies=companies,
            task_report_id=task_report_id,
            plane_company=plane_company
        )

        await callback.message.edit_text(
            f"🏢 **Выберите компанию**\n\n"
            f"{'_Первой показана компания из Plane_' if plane_company else ''}",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

        await callback.answer()

    except Exception as e:
        bot_logger.error(f"❌ Error in back_to_company callback: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


# ═══════════════════════════════════════════════════════════
# EDIT FIELD CALLBACKS
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("edit_field:"))
async def callback_edit_field(callback: CallbackQuery, state: FSMContext):
    """
    Admin wants to edit specific field from edit menu

    Callback format: edit_field:{field_name}:{task_report_id}
    Example: edit_field:duration:123
    """
    try:
        parts = callback.data.split(":")
        field_name = parts[1]
        task_report_id = int(parts[2])

        bot_logger.info(
            f"✏️ Admin {callback.from_user.id} wants to edit field '{field_name}' "
            f"for task report #{task_report_id}"
        )

        # BUG FIX #2: Load existing TaskReport and preserve metadata in state
        async for session in get_async_session():
            task_reports_service_inst = task_reports_service.TaskReportsService(session)
            task_report = await task_reports_service_inst.get_task_report(session, task_report_id)

            if not task_report:
                await callback.answer("❌ Отчёт не найден", show_alert=True)
                return

            # Preserve ALL existing metadata in FSM state
            await state.update_data(
                task_report_id=task_report_id,
                duration=task_report.work_duration,
                work_type=task_report.is_travel,
                company=task_report.company,
                workers=task_report.worker_names,
                editing_mode=True,  # Flag to return to preview after edit
                editing_field=field_name
            )

            bot_logger.info(
                f"📝 Preserved metadata: duration={task_report.work_duration}, "
                f"company={task_report.company}, workers={task_report.worker_names}"
            )

        # Route to appropriate handler based on field
        if field_name == "text":
            # Redirect to text editing
            await state.set_state(TaskReportStates.filling_report)
            await callback.message.edit_text(
                "📝 **Редактирование текста отчёта**\n\n"
                "Отправьте новый текст отчёта:",
                parse_mode="Markdown"
            )

        elif field_name == "duration":
            # Redirect to duration selection
            await state.set_state(TaskReportStates.filling_duration)
            keyboard = create_duration_keyboard(task_report_id)
            await callback.message.edit_text(
                "⏱️ **Редактирование длительности**\n\n"
                "Выберите новую длительность:",
                parse_mode="Markdown",
                reply_markup=keyboard
            )

        elif field_name == "work_type":
            # Redirect to work type selection
            await state.set_state(TaskReportStates.filling_work_type)
            keyboard = create_work_type_keyboard(task_report_id)
            await callback.message.edit_text(
                "🚗 **Редактирование типа работы**\n\n"
                "Был ли выезд к клиенту?",
                parse_mode="Markdown",
                reply_markup=keyboard
            )

        elif field_name == "company":
            # Redirect to company selection
            await state.set_state(TaskReportStates.filling_company)

            async for session in get_async_session():
                wj_service = work_journal_service.WorkJournalService(session)
            companies = await wj_service.get_companies()

            state_data = await state.get_data()
            plane_company = state_data.get("plane_project_name")

            keyboard = create_company_keyboard(
                companies=companies,
                task_report_id=task_report_id,
                plane_company=plane_company
            )

            await callback.message.edit_text(
                "🏢 **Редактирование компании**\n\n"
                "Выберите компанию:",
                parse_mode="Markdown",
                reply_markup=keyboard
            )

        elif field_name == "workers":
            # Redirect to workers selection
            await state.set_state(TaskReportStates.filling_workers)

            async for session in get_async_session():
                wj_service = work_journal_service.WorkJournalService(session)
                workers = await wj_service.get_workers()
                task_report = await task_reports_service.get_task_report(session, task_report_id)

            # Get current workers from DB
            current_workers = []
            if task_report and task_report.workers:
                try:
                    current_workers = json.loads(task_report.workers)
                except:
                    pass

            state_data = await state.get_data()
            plane_assignees = state_data.get("plane_assignees", [])

            # Update FSM state with current workers
            await state.update_data(selected_workers=current_workers)

            keyboard = create_workers_keyboard(
                workers=workers,
                task_report_id=task_report_id,
                selected_workers=current_workers,
                plane_assignees=plane_assignees
            )

            await callback.message.edit_text(
                "👥 **Редактирование исполнителей**\n\n"
                "Выберите исполнителей:",
                parse_mode="Markdown",
                reply_markup=keyboard
            )

        await callback.answer()

    except Exception as e:
        bot_logger.error(f"❌ Error in edit_field callback: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)
