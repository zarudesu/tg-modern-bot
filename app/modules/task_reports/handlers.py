"""
Task Reports Handlers - FSM-based report filling workflow

Admin receives notification → fills report → reviews → sends to client
"""

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from .states import TaskReportStates
from ...database.database import get_async_session
from ...services.task_reports_service import task_reports_service
from ...services import work_journal_service
from ...utils.logger import bot_logger
from ...utils.keyboards import get_back_to_main_menu_keyboard
from ...config import settings
from datetime import datetime
import json


router = Router(name="task_reports_handlers")

# ═══════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════

def parse_report_id_safely(callback_data: str, index: int = 1) -> int:
    """
    Safely parse report_id from callback_data
    
    Args:
        callback_data: The callback data string
        index: Index of report_id in split array (default 1)
    
    Returns:
        int: The report_id
    
    Raises:
        ValueError: If report_id is invalid or "None"
    """
    try:
        from ...utils.logger import bot_logger
        parts = callback_data.split(":")
        report_id_str = parts[index]
        
        if report_id_str == "None" or not report_id_str or report_id_str == "null":
            raise ValueError(f"Invalid report_id: '{report_id_str}'")
        
        return int(report_id_str)
    
    except (IndexError, ValueError) as e:
        from ...utils.logger import bot_logger
        bot_logger.error(f"Error parsing report_id from callback_data '{callback_data}': {e}")
        raise ValueError(f"Invalid callback data format")



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
            from ...integrations.plane import plane_api

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

                autofill_notice = ""
                if task_report.auto_filled_from_journal:
                    autofill_notice = "\n\n✅ _Автоматически заполнено из work journal_"

                await callback.message.edit_text(
                    f"📝 **Заполнение отчёта для задачи #{task_report.plane_sequence_id}**\n\n"
                    f"**Текущий текст отчёта:**\n{preview_text}{autofill_notice}\n\n"
                    f"Отправьте новый текст отчёта или согласуйте текущий:",
                    parse_mode="Markdown",
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
                from ..task_reports.keyboards import create_duration_keyboard

                await callback.message.edit_text(
                    f"📝 **Заполнение отчёта для задачи #{task_report.plane_sequence_id}**\n\n"
                    f"**Название задачи:** {task_report.task_title}\n\n"
                    f"⏱️ **Шаг 1/4:** Выберите длительность работы:",
                    parse_mode="Markdown",
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
                "Пожалуйста, опишите выполненную работу подробнее.",
                parse_mode="Markdown"
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
            from .keyboards import create_duration_keyboard
            keyboard = create_duration_keyboard(task_report_id)

            await message.reply(
                f"✅ **Текст отчёта сохранён!**\n\n"
                f"⏱️ **Укажите длительность работы**\n\n"
                f"Выберите из предложенных вариантов или укажите своё время:",
                parse_mode="Markdown",
                reply_markup=keyboard
            )

    except Exception as e:
        bot_logger.error(f"❌ Error handling report text: {e}")
        await message.reply("❌ Произошла ошибка при сохранении отчёта")
        await state.clear()


# ═══════════════════════════════════════════════════════════
# CALLBACK: APPROVE AND SEND TO CLIENT
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("approve_report:"))
async def callback_approve_report(callback: CallbackQuery, state: FSMContext):
    """
    Admin approves autofilled report without changes
    """
    try:
        try:
            task_report_id = parse_report_id_safely(callback.data)
        except ValueError as e:
            bot_logger.error(f"Invalid report_id in callback: {e}")
            await callback.answer("❌ Неверный ID отчёта", show_alert=True)
            return

        async for session in get_async_session():
            # Approve report
            task_report = await task_reports_service.approve_report(session, task_report_id)

            if not task_report:
                await callback.answer("❌ Отчёт не найден", show_alert=True)
                return

            # Move to review state
            await state.set_state(TaskReportStates.reviewing_report)
            await state.update_data(task_report_id=task_report_id)

            # Show confirmation
            await callback.message.edit_text(
                f"✅ **Отчёт одобрен!**\n\n"
                f"**Задача:** #{task_report.plane_sequence_id}\n\n"
                f"Отправить клиенту?",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="✅ Да, отправить",
                        callback_data=f"send_report:{task_report_id}"
                    )],
                    [InlineKeyboardButton(
                        text="✏️ Редактировать",
                        callback_data=f"edit_report:{task_report_id}"
                    )],
                    [InlineKeyboardButton(
                        text="❌ Отменить",
                        callback_data=f"cancel_report:{task_report_id}"
                    )]
                ])
            )

            await callback.answer()

    except Exception as e:
        bot_logger.error(f"❌ Error in approve_report callback: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("send_report:"))
async def callback_send_report(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Admin confirms sending report to client
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

            if not task_report.client_chat_id:
                await callback.answer(
                    "❌ Не указан chat_id клиента. Невозможно отправить отчёт.",
                    show_alert=True
                )
                return

            # Send to client
            try:
                client_message = (
                    f"✅ **Ваша заявка #{task_report.plane_sequence_id} выполнена!**\n\n"
                    f"**Название:** {task_report.task_title}\n\n"
                    f"**Отчёт о выполненной работе:**\n\n{task_report.report_text}"
                )

                await bot.send_message(
                    chat_id=task_report.client_chat_id,
                    text=client_message,
                    parse_mode="Markdown",
                    reply_to_message_id=task_report.client_message_id  # Reply to original request
                )

                bot_logger.info(
                    f"✅ Sent report #{task_report_id} to client chat {task_report.client_chat_id}"
                )

                # Mark as sent
                await task_reports_service.mark_sent_to_client(session, task_report_id)

                # Notify admin
                from ...utils.keyboards import get_back_to_main_menu_keyboard

                await callback.message.edit_text(
                    f"✅ **Отчёт отправлен клиенту!**\n\n"
                    f"Задача #{task_report.plane_sequence_id} завершена.",
                    reply_markup=get_back_to_main_menu_keyboard(),
                    parse_mode="Markdown"
                )

                # Clear FSM state
                await state.clear()

            except Exception as send_error:
                bot_logger.error(f"❌ Error sending report to client: {send_error}")
                await callback.answer(
                    f"❌ Ошибка отправки клиенту: {send_error}",
                    show_alert=True
                )

            await callback.answer()

    except Exception as e:
        bot_logger.error(f"❌ Error in send_report callback: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


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
            import json

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

        from ...utils.keyboards import get_back_to_main_menu_keyboard

        await callback.message.edit_text(
            "❌ Заполнение отчёта отменено.\n\n"
            "Напоминание будет отправлено позже.",
            reply_markup=get_back_to_main_menu_keyboard(),
            parse_mode="Markdown"
        )

        # Clear FSM state
        await state.clear()

        await callback.answer()

    except Exception as e:
        bot_logger.error(f"❌ Error in cancel_report callback: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


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
            import json
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


# ═══════════════════════════════════════════════════════════
# CALLBACK: APPROVE AND SEND (with client)
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("approve_send:"))
async def callback_approve_send(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Approve and send report to client immediately (client exists)
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
                await callback.answer("❌ Отчёт не заполнен", show_alert=True)
                return

            if not task_report.client_chat_id:
                await callback.answer(
                    "❌ Нет привязки к клиенту. Используйте 'Одобрить (без отправки)'",
                    show_alert=True
                )
                return

            # Approve report
            await task_reports_service.approve_report(session, task_report_id)

            # Send to client
            try:
                client_message = (
                    f"✅ **Ваша заявка #{task_report.plane_sequence_id} выполнена!**\n\n"
                    f"**Название:** {task_report.task_title}\n\n"
                    f"**Отчёт о выполненной работе:**\n\n{task_report.report_text}"
                )

                await bot.send_message(
                    chat_id=task_report.client_chat_id,
                    text=client_message,
                    parse_mode="Markdown",
                    reply_to_message_id=task_report.client_message_id
                )

                bot_logger.info(
                    f"✅ Sent report #{task_report_id} to client chat {task_report.client_chat_id}"
                )

                # Mark as sent
                await task_reports_service.mark_sent_to_client(session, task_report_id)

                # Notify admin
                from ...utils.keyboards import get_back_to_main_menu_keyboard

                await callback.message.edit_text(
                    f"✅ **Отчёт одобрен и отправлен клиенту!**\n\n"
                    f"Задача #{task_report.plane_sequence_id} завершена.",
                    reply_markup=get_back_to_main_menu_keyboard(),
                    parse_mode="Markdown"
                )

                # Clear state
                await state.clear()

            except Exception as send_error:
                bot_logger.error(f"❌ Error sending report to client: {send_error}")
                await callback.answer(
                    f"❌ Ошибка отправки: {send_error}",
                    show_alert=True
                )

            await callback.answer()

    except Exception as e:
        bot_logger.error(f"❌ Error in approve_send callback: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


# ═══════════════════════════════════════════════════════════
# CALLBACK: APPROVE ONLY (without client)
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("approve_only:"))
async def callback_approve_only(callback: CallbackQuery, state: FSMContext):
    """
    Approve report without sending to client (no client linked)
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
                await callback.answer("❌ Отчёт не заполнен", show_alert=True)
                return

            # Validate required fields before work_journal creation
            if not task_report.company:
                await callback.answer("❌ Компания не указана", show_alert=True)
                return

            if not task_report.work_duration:
                await callback.answer("❌ Длительность не указана", show_alert=True)
                return

            # Approve report
            await task_reports_service.approve_report(session, task_report_id)

            bot_logger.info(
                f"✅ Approved report #{task_report_id} without sending (no client linked)"
            )

            # Parse workers JSON
            workers_list = []
            if task_report.workers:
                try:
                    workers_list = json.loads(task_report.workers)
                except Exception as e:
                    bot_logger.warning(f"Failed to parse workers JSON: {e}")

            # Get user info
            from ...database.models import BotUser
            user = await session.get(BotUser, callback.from_user.id)

            if user:
                creator_name = f"@{user.username}" if user.username else (user.first_name or f"User_{callback.from_user.id}")
                user_email = f"{user.username}@example.com" if user.username else f"user_{callback.from_user.id}@telegram.bot"
            else:
                creator_name = f"User_{callback.from_user.id}"
                user_email = f"user_{callback.from_user.id}@telegram.bot"

            # Create work journal entry
            wj_service = work_journal_service.WorkJournalService(session)
            work_date = task_report.closed_at.date() if task_report.closed_at else datetime.now().date()

            bot_logger.info(
                f"📝 Creating work_journal entry for task report #{task_report_id}: "
                f"date={work_date}, company={task_report.company}, duration={task_report.work_duration}"
            )

            entry = await wj_service.create_work_entry(
                telegram_user_id=callback.from_user.id,
                user_email=user_email,
                work_date=work_date,
                company=task_report.company,
                work_duration=task_report.work_duration,
                work_description=task_report.report_text or "",
                is_travel=task_report.is_travel or False,
                worker_names=workers_list,
                created_by_user_id=callback.from_user.id,
                created_by_name=creator_name
            )

            # Link to task report
            task_report.work_journal_entry_id = entry.id
            await session.commit()

            bot_logger.info(
                f"✅ Created work_journal entry #{entry.id} linked to task report #{task_report_id}"
            )

            # Send to n8n (Google Sheets)
            try:
                from ...services.n8n_integration_service import N8nIntegrationService

                user_data = {
                    "first_name": user.first_name if user else callback.from_user.first_name,
                    "username": user.username if user else callback.from_user.username
                }

                n8n_service = N8nIntegrationService()
                bot_logger.info(f"Sending entry {entry.id} to n8n for Google Sheets sync")
                success = await n8n_service.send_with_retry(entry, user_data, session)
                if success:
                    bot_logger.info(f"✅ Successfully sent entry {entry.id} to n8n")
                else:
                    bot_logger.error(f"❌ Failed to send entry {entry.id} to n8n after retries")
            except Exception as e:
                bot_logger.error(f"Error sending to n8n for entry {entry.id}: {e}")
                # Don't stop the process, entry is already saved

            # Send group chat notification with worker mentions
            try:
                from ...services.worker_mention_service import WorkerMentionService

                if settings.work_journal_group_chat_id:
                    bot_logger.info(f"Sending group notification for entry {entry.id}")
                    mention_service = WorkerMentionService(session, callback.bot)

                    success, errors = await mention_service.send_work_assignment_notifications(
                        entry, creator_name, settings.work_journal_group_chat_id
                    )

                    if success:
                        bot_logger.info(f"✅ Successfully sent group notification for entry {entry.id}")

                    if errors:
                        for error in errors[:2]:
                            bot_logger.warning(f"Group notification error: {error}")
                else:
                    bot_logger.warning("WORK_JOURNAL_GROUP_CHAT_ID not configured - skipping group notification")

            except Exception as e:
                bot_logger.error(f"Error sending group notifications: {e}")
                # Don't stop the process

            # Notify admin with main menu
            from ...utils.keyboards import get_back_to_main_menu_keyboard

            await callback.message.edit_text(
                f"✅ **Отчёт одобрен!**\n\n"
                f"Задача #{task_report.plane_sequence_id} завершена.\n\n"
                f"⚠️ Отчёт не был отправлен клиенту (нет привязки).\n"
                f"📋 Отчёт сохранён в базе данных и добавлен в журнал работ.",
                reply_markup=get_back_to_main_menu_keyboard(),
                parse_mode="Markdown"
            )

            # Clear state
            await state.clear()
            await callback.answer()

    except Exception as e:
        bot_logger.error(f"❌ Error in approve_only callback: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


# ═══════════════════════════════════════════════════════════
# CALLBACK: CLOSE WITHOUT REPORT (admin decision)
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("close_no_report:"))
async def callback_close_no_report(callback: CallbackQuery, state: FSMContext):
    """
    Admin closes task without sending report to client

    Use cases:
    - No client linked to task
    - Internal task (no client notification needed)
    - Admin decision to skip client notification
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

            # Mark as cancelled (no client notification)
            await task_reports_service.close_without_report(session, task_report_id)

            bot_logger.info(
                f"✅ Admin {callback.from_user.id} closed TaskReport #{task_report_id} "
                f"without sending to client (Plane task #{task_report.plane_sequence_id})"
            )

            # Notify admin
            has_client = bool(task_report.client_chat_id)
            client_status = (
                f"✅ Клиент был привязан (chat_id={task_report.client_chat_id}), но отчёт не отправлен"
                if has_client
                else "⚠️ Клиент не был привязан к задаче"
            )

            from ...utils.keyboards import get_back_to_main_menu_keyboard

            await callback.message.edit_text(
                f"✅ **Задача закрыта без отчёта клиенту**\n\n"
                f"**Задача:** #{task_report.plane_sequence_id}\n"
                f"**Название:** {task_report.task_title}\n\n"
                f"{client_status}\n\n"
                f"📝 Задача завершена, отчёт сохранён в базе данных.",
                reply_markup=get_back_to_main_menu_keyboard(),
                parse_mode="Markdown"
            )

            # Clear state
            await state.clear()
            await callback.answer()

    except Exception as e:
        bot_logger.error(f"❌ Error in close_no_report callback: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)
