"""
Task Reports Metadata - Workers Handlers

Workers selection handlers (multiple choice with checkboxes)
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
import json

from ..states import TaskReportStates
from ..keyboards import create_workers_keyboard
from ..utils import parse_report_id_safely
from ....database.database import get_async_session
from ....services.task_reports_service import task_reports_service
from ....services import work_journal_service
from ....utils.logger import bot_logger


router = Router(name="task_reports_workers")


# ═══════════════════════════════════════════════════════════
# WORKERS SELECTION (MULTIPLE CHOICE)
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("tr_toggle_worker:"))
async def callback_toggle_worker(callback: CallbackQuery, state: FSMContext):
    """
    Admin toggles worker selection (checkbox)

    Callback format: tr_toggle_worker:{task_report_id}:{worker}
    Example: tr_toggle_worker:123:Zardes
    """
    try:
        parts = callback.data.split(":", 2)
        task_report_id = int(parts[1])
        worker = parts[2]

        # Get current selected workers from FSM state
        state_data = await state.get_data()
        selected_workers = state_data.get("selected_workers", [])

        # Toggle worker
        if worker in selected_workers:
            selected_workers.remove(worker)
            action = "unselected"
        else:
            selected_workers.append(worker)
            action = "selected"

        bot_logger.info(
            f"✅ Admin {callback.from_user.id} {action} worker '{worker}' "
            f"for task report #{task_report_id}. Total: {len(selected_workers)}"
        )

        # Save to FSM state
        await state.update_data(selected_workers=selected_workers)

        # Get workers and Plane assignees
        async for session in get_async_session():
            wj_service = work_journal_service.WorkJournalService(session)
            workers = await wj_service.get_workers()

        plane_assignees = state_data.get("plane_assignees", [])

        # Update keyboard with new selection
        keyboard = create_workers_keyboard(
            workers=workers,
            task_report_id=task_report_id,
            selected_workers=selected_workers,
            plane_assignees=plane_assignees
        )

        try:
            await callback.message.edit_reply_markup(reply_markup=keyboard)
        except Exception as edit_error:
            # If message hasn't changed, ignore error
            if "message is not modified" not in str(edit_error):
                raise

        await callback.answer(f"{'✅ Выбран' if action == 'selected' else '❌ Убран'}: {worker}")

    except Exception as e:
        bot_logger.error(f"❌ Error in toggle_worker callback: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("tr_workers_all_plane:"))
async def callback_workers_all_plane(callback: CallbackQuery, state: FSMContext):
    """
    Admin selects all workers from Plane assignees

    Callback format: tr_workers_all_plane:{task_report_id}
    """
    try:
        try:
            task_report_id = parse_report_id_safely(callback.data)
        except ValueError as e:
            bot_logger.error(f"Invalid report_id in callback: {e}")
            await callback.answer("❌ Неверный ID отчёта", show_alert=True)
            return

        # Get Plane assignees from FSM state
        state_data = await state.get_data()
        plane_assignees = state_data.get("plane_assignees", [])
        selected_workers = state_data.get("selected_workers", [])

        # Check if all Plane assignees are already selected
        all_selected = all(assignee in selected_workers for assignee in plane_assignees)

        if all_selected:
            # Deselect all Plane assignees
            selected_workers = [w for w in selected_workers if w not in plane_assignees]
            action = "deselected"
        else:
            # Select all Plane assignees
            for assignee in plane_assignees:
                if assignee not in selected_workers:
                    selected_workers.append(assignee)
            action = "selected"

        bot_logger.info(
            f"✅ Admin {callback.from_user.id} {action} all Plane workers "
            f"for task report #{task_report_id}. Total: {len(selected_workers)}"
        )

        # Save to FSM state
        await state.update_data(selected_workers=selected_workers)

        # Get workers from work_journal
        async for session in get_async_session():
            wj_service = work_journal_service.WorkJournalService(session)
            workers = await wj_service.get_workers()

        # Update keyboard with new selection
        keyboard = create_workers_keyboard(
            workers=workers,
            task_report_id=task_report_id,
            selected_workers=selected_workers,
            plane_assignees=plane_assignees
        )

        try:
            await callback.message.edit_reply_markup(reply_markup=keyboard)
        except Exception as edit_error:
            if "message is not modified" not in str(edit_error):
                raise

        await callback.answer(
            f"{'✅ Выбраны все из Plane' if action == 'selected' else '❌ Убраны все из Plane'}"
        )

    except Exception as e:
        bot_logger.error(f"❌ Error in workers_all_plane callback: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("tr_add_worker:"))
async def callback_add_worker(callback: CallbackQuery, state: FSMContext):
    """
    Admin wants to add a new worker (custom input)

    Callback format: tr_add_worker:{task_report_id}
    """
    try:
        try:
            task_report_id = parse_report_id_safely(callback.data)
        except ValueError as e:
            bot_logger.error(f"Invalid report_id in callback: {e}")
            await callback.answer("❌ Неверный ID отчёта", show_alert=True)
            return

        bot_logger.info(
            f"📝 Admin {callback.from_user.id} requested to add custom worker "
            f"for task report #{task_report_id}"
        )

        # Update FSM state to expect text input
        await state.set_state(TaskReportStates.filling_workers)
        await state.update_data(awaiting_custom_worker=True)

        await callback.message.edit_text(
            "👤 **Введите ФИО исполнителя**\n\n"
            "Напишите имя исполнителя (будет добавлен к списку):",
            parse_mode="Markdown"
        )

        await callback.answer()

    except Exception as e:
        bot_logger.error(f"❌ Error in add_worker callback: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.message(
    StateFilter(TaskReportStates.filling_workers),
    F.text
)
async def handle_custom_worker(message: Message, state: FSMContext):
    """
    Handle custom worker text input
    """
    try:
        state_data = await state.get_data()

        # Check if we're expecting custom worker input
        if not state_data.get("awaiting_custom_worker"):
            return

        task_report_id = state_data.get("task_report_id")
        worker = message.text.strip()

        # Validate length
        if len(worker) < 2:
            await message.reply(
                "❌ Имя исполнителя слишком короткое (минимум 2 символа).",
                parse_mode="Markdown"
            )
            return

        bot_logger.info(
            f"📝 Admin {message.from_user.id} added custom worker '{worker}' "
            f"for task report #{task_report_id}"
        )

        # Add to selected workers
        selected_workers = state_data.get("selected_workers", [])
        if worker not in selected_workers:
            selected_workers.append(worker)

        # Save to FSM state
        await state.update_data(
            selected_workers=selected_workers,
            awaiting_custom_worker=False
        )

        # Get workers from work_journal
        async for session in get_async_session():
            wj_service = work_journal_service.WorkJournalService(session)
            workers = await wj_service.get_workers()

        # Add custom worker to list if not present
        if worker not in workers:
            workers.append(worker)

        plane_assignees = state_data.get("plane_assignees", [])

        # Show updated workers keyboard
        keyboard = create_workers_keyboard(
            workers=workers,
            task_report_id=task_report_id,
            selected_workers=selected_workers,
            plane_assignees=plane_assignees
        )

        await message.reply(
            f"✅ Добавлен исполнитель: **{worker}**\n\n"
            f"👥 **Выберите исполнителей**\n\n"
            f"Можно выбрать несколько:",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

    except Exception as e:
        bot_logger.error(f"❌ Error handling custom worker: {e}")
        await message.reply("❌ Произошла ошибка при добавлении исполнителя")


@router.callback_query(F.data.startswith("tr_confirm_workers:"))
async def callback_confirm_workers(callback: CallbackQuery, state: FSMContext):
    """
    Admin confirms worker selection and proceeds to final preview

    Callback format: tr_confirm_workers:{task_report_id}
    """
    try:
        try:
            task_report_id = parse_report_id_safely(callback.data)
        except ValueError as e:
            bot_logger.error(f"Invalid report_id in callback: {e}")
            await callback.answer("❌ Неверный ID отчёта", show_alert=True)
            return

        # Get selected workers from FSM state
        state_data = await state.get_data()
        selected_workers = state_data.get("selected_workers", [])

        if not selected_workers:
            await callback.answer("❌ Выберите хотя бы одного исполнителя", show_alert=True)
            return

        bot_logger.info(
            f"✅ Admin {callback.from_user.id} confirmed workers {selected_workers} "
            f"for task report #{task_report_id}"
        )

        # Save to database
        async for session in get_async_session():
            await task_reports_service.update_metadata(
                session=session,
                task_report_id=task_report_id,
                workers=json.dumps(selected_workers)  # Store as JSON array
            )

        # Check if we're in editing mode
        editing_mode = state_data.get('editing_mode', False)

        if editing_mode:
            # Return to preview after editing - trigger preview callback
            bot_logger.info(f"📝 Editing mode: returning to preview after workers update")

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

        # Continue with normal flow (initial fill)
        bot_logger.info(
            f"📊 Metadata collected for task #{task_report_id}: "
            f"duration={state_data.get('work_duration')}, "
            f"type={'Travel' if state_data.get('is_travel') else 'Remote'}, "
            f"company={state_data.get('company')}, "
            f"workers={selected_workers}, "
            f"plane_assignees={state_data.get('plane_assignees', [])}"
        )

        # АВТОЗАПОЛНЕНИЕ: Генерация report_text из комментариев Plane (если не заполнен)
        async for session in get_async_session():
            task_report = await task_reports_service.get_task_report(session, task_report_id)

            if not task_report:
                await callback.answer("❌ Ошибка загрузки отчёта", show_alert=True)
                return

            # Если report_text пустой - автозаполняем из Plane комментариев
            if not task_report.report_text:
                bot_logger.info(f"📝 Auto-generating report text from Plane comments for task #{task_report_id}")
                success = await task_reports_service.fetch_and_generate_report_from_plane(session, task_report)
                if not success:
                    bot_logger.warning(f"⚠️ Could not auto-fill from Plane for task #{task_report_id}")
                # Перезагружаем task_report после автозаполнения
                task_report = await task_reports_service.get_task_report(session, task_report_id)

            # Show "Preview" button (not the full preview itself)
            from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

            await callback.message.edit_text(
                f"✅ **Метаданные собраны!**\n\n"
                f"**Задача:** #{task_report.plane_sequence_id}\n"
                f"⏱️ Длительность: **{task_report.work_duration or '⚠️ Не указано'}**\n"
                f"🚗 Тип работы: **{'Выезд' if task_report.is_travel else 'Удалённо'}**\n"
                f"🏢 Компания: **{task_report.company or '⚠️ Не указано'}**\n"
                f"👥 Исполнители: **{', '.join(selected_workers) if selected_workers else '⚠️ Не указано'}**\n\n"
                f"{'✅ Отчёт автоматически заполнен из Plane' if task_report.report_text else '⚠️ Отчёт пустой - заполните вручную'}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="👁️ Предпросмотр отчёта",
                        callback_data=f"preview_report:{task_report_id}"
                    )],
                    [InlineKeyboardButton(
                        text="❌ Отменить",
                        callback_data=f"cancel_report:{task_report_id}"
                    )]
                ])
            )

            await callback.answer()

    except Exception as e:
        bot_logger.error(f"❌ Error in confirm_workers callback: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)
