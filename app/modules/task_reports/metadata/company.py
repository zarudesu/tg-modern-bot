"""
Task Reports Metadata - Company Handlers

Company selection handlers with quick buttons and custom input
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from ..states import TaskReportStates
from ..keyboards import create_company_keyboard, create_workers_keyboard
from ..utils import parse_report_id_safely, map_company_name
from ....database.database import get_async_session
from ....services.task_reports_service import task_reports_service
from ....services import work_journal_service
from ....utils.logger import bot_logger


router = Router(name="task_reports_company")


# ═══════════════════════════════════════════════════════════
# COMPANY SELECTION
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("tr_company:"))
async def callback_company(callback: CallbackQuery, state: FSMContext):
    """
    Admin selects company from buttons

    Callback format: tr_company:{task_report_id}:{company}
    Example: tr_company:123:ACME Corp
    """
    try:
        parts = callback.data.split(":", 2)
        task_report_id = int(parts[1])
        selected_company = parts[2]

        # BUG FIX #3: Map company name from Plane to Russian
        company = map_company_name(selected_company)

        bot_logger.info(
            f"🔘 Admin {callback.from_user.id} selected company '{company}' "
            f"(original: '{selected_company}') for task report #{task_report_id}"
        )

        # Save to FSM state
        await state.update_data(company=company)

        # Save to database
        async for session in get_async_session():
            await task_reports_service.update_metadata(
                session=session,
                task_report_id=task_report_id,
                company=company
            )

        # Check if we're in editing mode
        state_data = await state.get_data()
        editing_mode = state_data.get('editing_mode', False)

        if editing_mode:
            # Return to preview after editing - trigger preview callback
            bot_logger.info(f"📝 Editing mode: returning to preview after company update")

            # Clear editing mode flag
            await state.update_data(editing_mode=False)

            # Trigger preview_report callback
            from aiogram.types import CallbackQuery as FakeCallback
            fake_callback = type('obj', (object,), {
                'data': f'preview_report:{task_report_id}',
                'from_user': callback.from_user,
                'message': callback.message,
                'answer': callback.answer
            })()

            # Import and call preview handler
            from ..handlers.preview import callback_preview_report
            await callback_preview_report(fake_callback)
            return
        else:
            # Continue to next step (workers selection)
            await state.set_state(TaskReportStates.filling_workers)

            # Get workers from work_journal
            async for session in get_async_session():
                wj_service = work_journal_service.WorkJournalService(session)
                workers = await wj_service.get_workers()

            # Get Plane assignees from FSM state
            plane_assignees = state_data.get("plane_assignees", [])

            # Auto-select Plane assignees on first show
            selected_workers = plane_assignees.copy() if plane_assignees else []

            # Save to FSM state
            await state.update_data(selected_workers=selected_workers)

            bot_logger.info(
                f"📋 Auto-selected Plane assignees for task report #{task_report_id}: {selected_workers}"
            )

            # Show workers keyboard
            keyboard = create_workers_keyboard(
                workers=workers,
                task_report_id=task_report_id,
                selected_workers=selected_workers,  # Auto-selected from Plane
                plane_assignees=plane_assignees
            )

            await callback.message.edit_text(
                f"✅ Компания: **{company}**\n\n"
                f"👥 **Выберите исполнителей**\n\n"
                f"{'_Исполнители из Plane помечены_' if plane_assignees else ''}\n"
                f"Можно выбрать несколько:",
                reply_markup=keyboard
            )

            await callback.answer()

    except Exception as e:
        bot_logger.error(f"❌ Error in company callback: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("tr_custom_company:"))
async def callback_custom_company(callback: CallbackQuery, state: FSMContext):
    """
    Admin wants to enter custom company

    Callback format: tr_custom_company:{task_report_id}
    """
    try:
        try:
            task_report_id = parse_report_id_safely(callback.data)
        except ValueError as e:
            bot_logger.error(f"Invalid report_id in callback: {e}")
            await callback.answer("❌ Неверный ID отчёта", show_alert=True)
            return

        bot_logger.info(
            f"📝 Admin {callback.from_user.id} requested custom company "
            f"for task report #{task_report_id}"
        )

        # Update FSM state to expect text input
        await state.set_state(TaskReportStates.filling_company)
        await state.update_data(awaiting_custom_company=True)

        await callback.message.edit_text(
            "🏢 **Введите название компании**\n\n"
            "Напишите название компании (будет сохранено для дальнейшего использования):",
            
        )

        await callback.answer()

    except Exception as e:
        bot_logger.error(f"❌ Error in custom_company callback: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.message(
    StateFilter(TaskReportStates.filling_company),
    F.text
)
async def handle_custom_company(message: Message, state: FSMContext):
    """
    Handle custom company text input
    """
    try:
        state_data = await state.get_data()

        # Check if we're expecting custom company input
        if not state_data.get("awaiting_custom_company"):
            return

        task_report_id = state_data.get("task_report_id")
        company = message.text.strip()

        # Validate length
        if len(company) < 2:
            await message.reply(
                "❌ Название компании слишком короткое (минимум 2 символа).",
                
            )
            return

        bot_logger.info(
            f"📝 Admin {message.from_user.id} entered custom company '{company}' "
            f"for task report #{task_report_id}"
        )

        # Save to FSM state
        await state.update_data(
            company=company,
            awaiting_custom_company=False
        )

        # Save to database
        async for session in get_async_session():
            await task_reports_service.update_metadata(
                session=session,
                task_report_id=task_report_id,
                company=company
            )

        # Move to workers selection
        await state.set_state(TaskReportStates.filling_workers)

        # Get workers from work_journal
        async for session in get_async_session():
            wj_service = work_journal_service.WorkJournalService(session)
            workers = await wj_service.get_workers()

        # Get Plane assignees from FSM state
        plane_assignees = state_data.get("plane_assignees", [])

        # Show workers keyboard
        keyboard = create_workers_keyboard(
            workers=workers,
            task_report_id=task_report_id,
            selected_workers=[],
            plane_assignees=plane_assignees
        )

        await message.reply(
            f"✅ Компания: **{company}**\n\n"
            f"👥 **Выберите исполнителей**\n\n"
            f"{'_Исполнители из Plane помечены_' if plane_assignees else ''}\n"
            f"Можно выбрать несколько:",
            reply_markup=keyboard
        )

    except Exception as e:
        bot_logger.error(f"❌ Error handling custom company: {e}")
        await message.reply("❌ Произошла ошибка при сохранении компании")
