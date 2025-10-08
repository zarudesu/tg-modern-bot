"""
Task Reports Approval Handlers

Handlers for approving, sending, and rejecting reports
"""

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from ..states import TaskReportStates
from ..utils import parse_report_id_safely, escape_markdown_v2
from ....database.database import get_async_session
from ....services.task_reports_service import task_reports_service
from ....services import work_journal_service
from ....utils.logger import bot_logger
from ....utils.keyboards import get_back_to_main_menu_keyboard
from ....config import settings
from datetime import datetime
import json


router = Router(name="task_reports_approval")


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

    BUG FIX #4: Apply markdown escaping to prevent Telegram API errors
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
                # BUG FIX #4: Escape markdown to prevent API errors
                client_message = (
                    f"✅ **Ваша заявка #{task_report.plane_sequence_id} выполнена!**\\n\\n"
                    f"**Название:** {escape_markdown_v2(task_report.task_title)}\\n\\n"
                    f"**Отчёт о выполненной работе:**\\n\\n{escape_markdown_v2(task_report.report_text)}"
                )

                await bot.send_message(
                    chat_id=task_report.client_chat_id,
                    text=client_message,
                    parse_mode="MarkdownV2",
                    reply_to_message_id=task_report.client_message_id  # Reply to original request
                )

                bot_logger.info(
                    f"✅ Sent report #{task_report_id} to client chat {task_report.client_chat_id}"
                )

                # Mark as sent
                await task_reports_service.mark_sent_to_client(session, task_report_id)

                # Notify admin
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
# CALLBACK: APPROVE AND SEND (with client)
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("approve_send:"))
async def callback_approve_send(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Approve and send report to client immediately (client exists)

    BUG FIX #4: Apply markdown escaping to prevent Telegram API errors
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
                # BUG FIX #4: Escape markdown to prevent API errors
                client_message = (
                    f"✅ **Ваша заявка #{task_report.plane_sequence_id} выполнена!**\\n\\n"
                    f"**Название:** {escape_markdown_v2(task_report.task_title)}\\n\\n"
                    f"**Отчёт о выполненной работе:**\\n\\n{escape_markdown_v2(task_report.report_text)}"
                )

                await bot.send_message(
                    chat_id=task_report.client_chat_id,
                    text=client_message,
                    parse_mode="MarkdownV2",
                    reply_to_message_id=task_report.client_message_id
                )

                bot_logger.info(
                    f"✅ Sent report #{task_report_id} to client chat {task_report.client_chat_id}"
                )

                # Mark as sent
                await task_reports_service.mark_sent_to_client(session, task_report_id)

                # Notify admin
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
            from ....database.models import BotUser
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
                from ....services.n8n_integration_service import N8nIntegrationService

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
                from ....services.worker_mention_service import WorkerMentionService

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
