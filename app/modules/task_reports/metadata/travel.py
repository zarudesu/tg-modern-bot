"""
Task Reports Metadata - Work Type Handlers

Work type (Travel/Remote) selection handlers
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from ..states import TaskReportStates
from ..keyboards import create_work_type_keyboard, create_company_keyboard
from ....database.database import get_async_session
from ....services.task_reports_service import task_reports_service
from ....services import work_journal_service
from ....utils.logger import bot_logger


router = Router(name="task_reports_travel")


# ═══════════════════════════════════════════════════════════
# WORK TYPE SELECTION
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("tr_travel:"))
async def callback_work_type(callback: CallbackQuery, state: FSMContext):
    """
    Admin selects work type (Travel / Remote)

    Callback format: tr_travel:{task_report_id}:yes/no
    Example: tr_travel:123:yes
    """
    try:
        parts = callback.data.split(":")
        task_report_id = int(parts[1])
        is_travel = parts[2] == "yes"

        work_type_display = "Выезд" if is_travel else "Удалённо"

        bot_logger.info(
            f"🔘 Admin {callback.from_user.id} selected work type '{work_type_display}' "
            f"for task report #{task_report_id}"
        )

        # Save to FSM state
        await state.update_data(is_travel=is_travel)

        # Save to database
        async for session in get_async_session():
            await task_reports_service.update_metadata(
                session=session,
                task_report_id=task_report_id,
                is_travel=is_travel
            )

        # Check if we're in editing mode
        state_data = await state.get_data()
        editing_mode = state_data.get('editing_mode', False)

        if editing_mode:
            # Return to preview after editing - trigger preview callback
            bot_logger.info(f"📝 Editing mode: returning to preview after work type update")

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
            # Continue to next step (company selection)
            await state.set_state(TaskReportStates.filling_company)

            # Get companies from work_journal
            async for session in get_async_session():
                wj_service = work_journal_service.WorkJournalService(session)
                companies = await wj_service.get_companies()

            # Get Plane company from FSM state
            plane_company = state_data.get("plane_project_name")

            # Show company keyboard
            keyboard = create_company_keyboard(
                companies=companies,
                task_report_id=task_report_id,
                plane_company=plane_company
            )

            await callback.message.edit_text(
                f"✅ Тип работы: **{work_type_display}**\n\n"
                f"🏢 **Выберите компанию**\n\n"
                f"{'_Первой показана компания из Plane_' if plane_company else ''}",
                reply_markup=keyboard
            )

            await callback.answer()

    except Exception as e:
        bot_logger.error(f"❌ Error in work_type callback: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)
