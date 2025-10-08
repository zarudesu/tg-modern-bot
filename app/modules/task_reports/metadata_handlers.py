"""
Task Reports Metadata Handlers - Button-Based UX

Handlers для заполнения метаданных через кнопки (как в work_journal)
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
import json

from .states import TaskReportStates
from .keyboards import (
    create_duration_keyboard,
    create_work_type_keyboard,
    create_company_keyboard,
    create_workers_keyboard
)
from ...database.database import get_async_session
from ...services.task_reports_service import task_reports_service
from ...services import work_journal_service
from ...utils.logger import bot_logger


router = Router(name="task_reports_metadata")


# ═══════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════

def parse_report_id_safely(callback_data: str, index: int = 1) -> int:
    """
    Safely parse report_id from callback_data

    Args:
        callback_data: The callback data string (e.g., "tr_duration:123:2h")
        index: Index of report_id in split array (default 1)

    Returns:
        int: The report_id

    Raises:
        ValueError: If report_id is invalid or "None"
    """
    try:
        parts = callback_data.split(":")
        report_id_str = parts[index]

        if report_id_str == "None" or not report_id_str or report_id_str == "null":
            raise ValueError(f"Invalid report_id: '{report_id_str}'")

        return int(report_id_str)

    except (IndexError, ValueError) as e:
        bot_logger.error(f"Error parsing report_id from callback_data '{callback_data}': {e}")
        raise ValueError(f"Invalid callback data format")


# ═══════════════════════════════════════════════════════════
# SECTION 1: DURATION SELECTION
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("agree_text:"))
async def callback_agree_text(callback: CallbackQuery, state: FSMContext):
    """
    Admin agrees with autofilled report text and proceeds to duration selection

    Callback format: agree_text:{task_report_id}
    """
    try:
        try:
            task_report_id = parse_report_id_safely(callback.data)
        except ValueError as e:
            bot_logger.error(f"Invalid report_id in callback: {e}")
            await callback.answer("❌ Неверный ID отчёта", show_alert=True)
            return
        bot_logger.info(f"✅ Admin {callback.from_user.id} agreed with text for report #{task_report_id}")

        # Move to duration selection
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
        bot_logger.error(f"❌ Error in agree_text callback: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("tr_duration:"))
async def callback_duration(callback: CallbackQuery, state: FSMContext):
    """
    Admin selects duration from quick buttons

    Callback format: tr_duration:{task_report_id}:{duration}
    Example: tr_duration:123:2h
    """
    try:
        parts = callback.data.split(":")
        task_report_id = int(parts[1])
        duration = parts[2]

        bot_logger.info(
            f"🔘 Admin {callback.from_user.id} selected duration '{duration}' "
            f"for task report #{task_report_id}"
        )

        # Save to FSM state
        await state.update_data(work_duration=duration)

        # Save to database
        async for session in get_async_session():
            await task_reports_service.update_metadata(
                session=session,
                task_report_id=task_report_id,
                work_duration=duration
            )

        # Move to work type selection
        await state.set_state(TaskReportStates.filling_work_type)

        # Show work type keyboard
        keyboard = create_work_type_keyboard(task_report_id)

        await callback.message.edit_text(
            f"✅ Длительность: **{duration}**\n\n"
            f"🚗 **Был ли выезд к клиенту?**",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

        await callback.answer()

    except Exception as e:
        bot_logger.error(f"❌ Error in duration callback: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("tr_custom_duration:"))
async def callback_custom_duration(callback: CallbackQuery, state: FSMContext):
    """
    Admin wants to enter custom duration

    Callback format: tr_custom_duration:{task_report_id}
    """
    try:
        try:
            task_report_id = parse_report_id_safely(callback.data)
        except ValueError as e:
            bot_logger.error(f"Invalid report_id in callback: {e}")
            await callback.answer("❌ Неверный ID отчёта", show_alert=True)
            return

        bot_logger.info(
            f"📝 Admin {callback.from_user.id} requested custom duration "
            f"for task report #{task_report_id}"
        )

        # Update FSM state to expect text input
        await state.set_state(TaskReportStates.filling_duration)
        await state.update_data(awaiting_custom_duration=True)

        await callback.message.edit_text(
            "⏱️ **Введите длительность работы**\n\n"
            "Примеры:\n"
            "• `2 часа`\n"
            "• `1.5 часа`\n"
            "• `30 мин`\n"
            "• `1 час 30 мин`\n\n"
            "Формат: количество + единица измерения",
            parse_mode="Markdown"
        )

        await callback.answer()

    except Exception as e:
        bot_logger.error(f"❌ Error in custom_duration callback: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.message(
    StateFilter(TaskReportStates.filling_duration),
    F.text
)
async def handle_custom_duration(message: Message, state: FSMContext):
    """
    Handle custom duration text input (Russian format like work_journal)

    Expected format: "2 часа", "30 мин", "1 час 30 мин", "1.5 часа"
    """
    try:
        state_data = await state.get_data()

        # Check if we're expecting custom duration input
        if not state_data.get("awaiting_custom_duration"):
            return

        task_report_id = state_data.get("task_report_id")
        text = message.text.strip()

        # Parse duration (same logic as work_journal/text_handlers.py:167-286)
        import re
        text_lower = text.lower()
        duration_minutes = None

        # Формат "2 часа", "1 час", "час"
        hour_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:ч|час|часа|часов|hours?)', text_lower)
        # Формат "30 мин", "минут"
        min_match = re.search(r'(\d+)\s*(?:мин|минут|минута|minutes?)', text_lower)

        if hour_match and min_match:
            # Если есть и часы и минуты: "1 час 30 мин"
            hours = float(hour_match.group(1))
            minutes = int(min_match.group(1))
            duration_minutes = int(hours * 60) + minutes
        elif hour_match:
            # Только часы: "2.5 часа", "1 час"
            hours = float(hour_match.group(1))
            duration_minutes = int(hours * 60)
        elif min_match:
            # Только минуты: "45 мин"
            duration_minutes = int(min_match.group(1))
        else:
            # Пытаемся как чистое число (минуты)
            try:
                duration_minutes = int(text)
            except ValueError:
                await message.reply(
                    "❌ **Неверный формат времени**\n\n"
                    "Введите время в формате:\n"
                    "• `2 часа`\n"
                    "• `30 мин`\n"
                    "• `1 час 30 мин`",
                    parse_mode="Markdown"
                )
                return

        # Валидация диапазона
        if duration_minutes <= 0:
            await message.reply("❌ Время должно быть больше 0 минут")
            return

        if duration_minutes > 1440:  # 24 часа
            await message.reply("❌ Максимальное время: 1440 минут (24 часа)")
            return

        # Форматируем время
        if duration_minutes < 60:
            formatted_duration = f"{duration_minutes} мин"
        else:
            hours = duration_minutes // 60
            minutes = duration_minutes % 60
            if minutes == 0:
                formatted_duration = f"{hours} ч"
            else:
                formatted_duration = f"{hours} ч {minutes} мин"

        bot_logger.info(
            f"📝 Admin {message.from_user.id} entered custom duration '{formatted_duration}' "
            f"for task report #{task_report_id}"
        )

        # Save to FSM state
        await state.update_data(
            work_duration=formatted_duration,
            awaiting_custom_duration=False
        )

        # Save to database
        async for session in get_async_session():
            await task_reports_service.update_metadata(
                session=session,
                task_report_id=task_report_id,
                work_duration=formatted_duration
            )

        # Move to work type selection
        await state.set_state(TaskReportStates.filling_work_type)

        # Show work type keyboard
        keyboard = create_work_type_keyboard(task_report_id)

        await message.reply(
            f"✅ Длительность: **{formatted_duration}**\n\n"
            f"🚗 **Был ли выезд к клиенту?**",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

    except Exception as e:
        bot_logger.error(f"❌ Error handling custom duration: {e}")
        await message.reply("❌ Произошла ошибка при сохранении длительности")


# ═══════════════════════════════════════════════════════════
# SECTION 2: WORK TYPE SELECTION
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

        # Move to company selection
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
            f"✅ Тип работы: **{work_type_display}**\n\n"
            f"🏢 **Выберите компанию**\n\n"
            f"{'_Первой показана компания из Plane_' if plane_company else ''}",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

        await callback.answer()

    except Exception as e:
        bot_logger.error(f"❌ Error in work_type callback: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


# ═══════════════════════════════════════════════════════════
# SECTION 3: COMPANY SELECTION
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
        company = parts[2]

        bot_logger.info(
            f"🔘 Admin {callback.from_user.id} selected company '{company}' "
            f"for task report #{task_report_id}"
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

        # Move to workers selection
        await state.set_state(TaskReportStates.filling_workers)

        # Get workers from work_journal
        async for session in get_async_session():
            wj_service = work_journal_service.WorkJournalService(session)
            workers = await wj_service.get_workers()

        # Get Plane assignees from FSM state
        state_data = await state.get_data()
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
            parse_mode="Markdown",
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
            parse_mode="Markdown"
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
                parse_mode="Markdown"
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
            parse_mode="Markdown",
            reply_markup=keyboard
        )

    except Exception as e:
        bot_logger.error(f"❌ Error handling custom company: {e}")
        await message.reply("❌ Произошла ошибка при сохранении компании")


# ═══════════════════════════════════════════════════════════
# SECTION 4: WORKERS SELECTION (MULTIPLE CHOICE)
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

            # Format preview
            preview = task_report.report_text[:2000] if task_report.report_text else "⚠️ Отчёт не заполнен"
            if task_report.report_text and len(task_report.report_text) > 2000:
                preview += "\n\n[...]"

            has_client = bool(task_report.client_chat_id)

            # Format metadata
            metadata_text = "\n**МЕТАДАННЫЕ РАБОТЫ:**\n"
            metadata_text += f"⏱️ Длительность: **{task_report.work_duration or '⚠️ Не указано'}**\n"
            metadata_text += f"🚗 Тип работы: **{'Выезд' if task_report.is_travel else 'Удалённо'}**\n" if task_report.is_travel is not None else "🚗 Тип работы: ⚠️ _Не указано_\n"
            metadata_text += f"🏢 Компания: **{task_report.company or '⚠️ Не указано'}**\n"

            if task_report.workers:
                try:
                    workers_list = json.loads(task_report.workers)
                    workers_display = ", ".join(workers_list)
                except:
                    workers_display = task_report.workers
                metadata_text += f"👥 Исполнители: **{workers_display}**\n"
            else:
                metadata_text += "👥 Исполнители: ⚠️ _Не указано_\n"

            # Build keyboard
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
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
        bot_logger.error(f"❌ Error in confirm_workers callback: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


# ═══════════════════════════════════════════════════════════
# SECTION 5: NAVIGATION (BACK BUTTONS)
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
# SECTION 6: EDIT FIELD CALLBACKS
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
