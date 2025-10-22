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
                f"✅ <b>Отчёт одобрен!</b>\n\n"
                f"<b>Задача:</b> #{task_report.plane_sequence_id}\n\n"
                f"Отправить клиенту?",
                parse_mode="HTML",
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
                # BUG FIX #4: Escape HTML to prevent API errors
                title_escaped = task_report.task_title.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                report_escaped = task_report.report_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

                client_message = (
                    f"✅ <b>Ваша заявка #{task_report.plane_sequence_id} выполнена!</b>\n\n"
                    f"<b>Название:</b> {title_escaped}\n\n"
                    f"<b>Отчёт о выполненной работе:</b>\n\n{report_escaped}"
                )

                await bot.send_message(
                    chat_id=task_report.client_chat_id,
                    text=client_message,
                    parse_mode="HTML",
                    reply_to_message_id=task_report.client_message_id  # Reply to original request
                )

                bot_logger.info(
                    f"✅ Sent report #{task_report_id} to client chat {task_report.client_chat_id}"
                )

                # Mark as sent
                await task_reports_service.mark_sent_to_client(session, task_report_id)

                # Notify admin
                await callback.message.edit_text(
                    f"✅ <b>Отчёт отправлен клиенту!</b>\n\n"
                    f"Задача #{task_report.plane_sequence_id} завершена.",
                    reply_markup=get_back_to_main_menu_keyboard(),
                    parse_mode="HTML"
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
                # BUG FIX #4: Escape HTML to prevent API errors
                title_escaped = task_report.task_title.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                report_escaped = task_report.report_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

                client_message = (
                    f"✅ <b>Ваша заявка #{task_report.plane_sequence_id} выполнена!</b>\n\n"
                    f"<b>Название:</b> {title_escaped}\n\n"
                    f"<b>Отчёт о выполненной работе:</b>\n\n{report_escaped}"
                )

                await bot.send_message(
                    chat_id=task_report.client_chat_id,
                    text=client_message,
                    parse_mode="HTML",
                    reply_to_message_id=task_report.client_message_id
                )

                bot_logger.info(
                    f"✅ Sent report #{task_report_id} to client chat {task_report.client_chat_id}"
                )

                # Mark as sent
                await task_reports_service.mark_sent_to_client(session, task_report_id)

                # BUG FIX #5: Add Google Sheets integration (missing in approve_send)
                # This should mirror approve_only handler (lines 312-385)

                # Validate required fields before work_journal creation
                if not task_report.company:
                    await callback.answer("❌ Компания не указана", show_alert=True)
                    return

                if not task_report.work_duration:
                    await callback.answer("❌ Длительность не указана", show_alert=True)
                    return

                if not task_report.workers:
                    await callback.answer("❌ Исполнители не указаны", show_alert=True)
                    return

                # Parse workers JSON
                workers_list = []
                if task_report.workers:
                    try:
                        workers_list = json.loads(task_report.workers)
                    except Exception as e:
                        bot_logger.warning(f"Failed to parse workers JSON: {e}")

                # Map telegram usernames to display names for Google Sheets/notifications
                from ..utils import map_workers_to_display_names_list
                workers_display_list = map_workers_to_display_names_list(workers_list)
                bot_logger.info(f"📝 Mapped workers: {workers_list} → {workers_display_list}")

                # Get user info (use Telegram API data, not DB - more up-to-date!)
                from ....database.models import BotUser
                user = await session.get(BotUser, callback.from_user.id)

                # Use callback.from_user for current username (not DB which can be stale)
                if callback.from_user.username:
                    creator_name = f"@{callback.from_user.username}"
                    user_email = f"{callback.from_user.username}@example.com"
                elif user and user.first_name:
                    creator_name = user.first_name
                    user_email = f"user_{callback.from_user.id}@telegram.bot"
                else:
                    creator_name = callback.from_user.first_name or f"User_{callback.from_user.id}"
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
                    worker_names=workers_display_list,  # Use display names for Google Sheets
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
                    bot_logger.info(f"📊 Sending entry {entry.id} to n8n for Google Sheets sync")
                    success = await n8n_service.send_with_retry(entry, user_data, session)
                    if success:
                        bot_logger.info(f"✅ Successfully sent entry {entry.id} to n8n (Google Sheets)")
                    else:
                        bot_logger.error(f"❌ Failed to send entry {entry.id} to n8n after retries")
                except Exception as e:
                    bot_logger.error(f"Error sending to n8n for entry {entry.id}: {e}")
                    # Don't stop the process, entry is already saved

                # Send group chat notification with worker mentions
                try:
                    from ....services.worker_mention_service import WorkerMentionService

                    if settings.work_journal_group_chat_id:
                        bot_logger.info(f"📢 Sending group notification for entry {entry.id}")
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

                # Notify admin with full details
                await callback.message.edit_text(
                    f"✅ <b>Отчёт одобрен и отправлен клиенту!</b>\n\n"
                    f"Задача #{task_report.plane_sequence_id} завершена.\n\n"
                    f"📋 Отчёт отправлен в чат клиента (reply)\n"
                    f"📊 Данные сохранены в Google Sheets\n"
                    f"👥 Уведомление отправлено в группу",
                    reply_markup=get_back_to_main_menu_keyboard(),
                    parse_mode="HTML"
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

            if not task_report.workers:
                await callback.answer("❌ Исполнители не указаны", show_alert=True)
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

            # Map telegram usernames to display names for Google Sheets/notifications
            from ..utils import map_workers_to_display_names_list
            workers_display_list = map_workers_to_display_names_list(workers_list)
            bot_logger.info(f"📝 Mapped workers: {workers_list} → {workers_display_list}")

            # Get user info (use Telegram API data, not DB - more up-to-date!)
            from ....database.models import BotUser
            user = await session.get(BotUser, callback.from_user.id)

            # Use callback.from_user for current username (not DB which can be stale)
            if callback.from_user.username:
                creator_name = f"@{callback.from_user.username}"
                user_email = f"{callback.from_user.username}@example.com"
            elif user and user.first_name:
                creator_name = user.first_name
                user_email = f"user_{callback.from_user.id}@telegram.bot"
            else:
                creator_name = callback.from_user.first_name or f"User_{callback.from_user.id}"
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
                worker_names=workers_display_list,  # Use display names for Google Sheets
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
                f"✅ <b>Отчёт одобрен!</b>\n\n"
                f"Задача #{task_report.plane_sequence_id} завершена.\n\n"
                f"⚠️ Отчёт не был отправлен клиенту (нет привязки).\n"
                f"📋 Отчёт сохранён в базе данных и добавлен в журнал работ.",
                reply_markup=get_back_to_main_menu_keyboard(),
                parse_mode="HTML"
            )

            # Clear state
            await state.clear()
            await callback.answer()

    except Exception as e:
        bot_logger.error(f"❌ Error in approve_only callback: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


# ═══════════════════════════════════════════════════════════
# CALLBACK: SEND TO GROUP (new feature)
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("send_to_group:"))
async def callback_send_to_group(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Send completed report to work journal group chat

    Sends full report text to group + creates work_journal entry + Google Sheets sync
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

            # Check if group chat ID is configured
            group_chat_id = settings.work_journal_group_chat_id

            if not group_chat_id:
                await callback.answer("❌ Group chat ID не настроен в конфиге", show_alert=True)
                return

            # Build report message for group
            task_title_escaped = task_report.task_title.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            company_escaped = (task_report.company or "Не указана").replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            report_text_escaped = task_report.report_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            duration_escaped = (task_report.work_duration or "Не указано").replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

            # Parse workers
            workers_list = []
            if task_report.workers:
                try:
                    workers_list = json.loads(task_report.workers)
                except Exception as e:
                    bot_logger.warning(f"Failed to parse workers JSON: {e}")

            # Map to mentions for group
            workers_text = ""
            if workers_list:
                from ..utils import map_workers_to_mentions
                workers_text = map_workers_to_mentions(workers_list)
            else:
                workers_text = "Не указаны"

            group_message = (
                f"📋 <b>Отчёт о выполнении задачи</b>\n\n"
                f"🎯 <b>Задача:</b> {task_title_escaped}\n"
                f"🏢 <b>Компания:</b> {company_escaped}\n"
                f"⏱️ <b>Время:</b> {duration_escaped}\n"
                f"👥 <b>Исполнители:</b> {workers_text}\n\n"
                f"━━━━━━━━━━━━━━━━\n\n"
                f"📝 <b>Отчёт:</b>\n\n{report_text_escaped}"
            )

            # Send to group
            try:
                await bot.send_message(
                    chat_id=group_chat_id,
                    text=group_message,
                    parse_mode="HTML"
                )

                bot_logger.info(f"✅ Sent report #{task_report_id} to group chat {group_chat_id}")

            except Exception as send_error:
                bot_logger.error(f"❌ Error sending report to group: {send_error}")
                await callback.answer(f"❌ Ошибка отправки в группу: {send_error}", show_alert=True)
                return

            # Approve report (if not already)
            if task_report.status != 'approved':
                await task_reports_service.approve_report(session, task_report_id)

            # Now create work_journal entry if required fields are present
            if task_report.company and task_report.work_duration and workers_list:
                # Map telegram usernames to display names
                from ..utils import map_workers_to_display_names_list
                workers_display_list = map_workers_to_display_names_list(workers_list)

                # Get user info
                from ....database.models import BotUser
                user = await session.get(BotUser, callback.from_user.id)

                if callback.from_user.username:
                    creator_name = f"@{callback.from_user.username}"
                    user_email = f"{callback.from_user.username}@example.com"
                else:
                    creator_name = callback.from_user.first_name or f"User_{callback.from_user.id}"
                    user_email = f"user_{callback.from_user.id}@telegram.bot"

                # Create work journal entry
                wj_service = work_journal_service.WorkJournalService(session)
                work_date = task_report.closed_at.date() if task_report.closed_at else datetime.now().date()

                entry = await wj_service.create_work_entry(
                    telegram_user_id=callback.from_user.id,
                    user_email=user_email,
                    work_date=work_date,
                    company=task_report.company,
                    work_duration=task_report.work_duration,
                    work_description=task_report.report_text or "",
                    is_travel=task_report.is_travel or False,
                    worker_names=workers_display_list,
                    created_by_user_id=callback.from_user.id,
                    created_by_name=creator_name
                )

                # Link to task report
                task_report.work_journal_entry_id = entry.id
                await session.commit()

                bot_logger.info(f"✅ Created work_journal entry #{entry.id} linked to task report #{task_report_id}")

                # Send to n8n (Google Sheets)
                try:
                    from ....services.n8n_integration_service import N8nIntegrationService

                    user_data = {
                        "first_name": user.first_name if user else callback.from_user.first_name,
                        "username": user.username if user else callback.from_user.username
                    }

                    n8n_service = N8nIntegrationService()
                    success = await n8n_service.send_with_retry(entry, user_data, session)
                    if success:
                        bot_logger.info(f"✅ Successfully sent entry {entry.id} to n8n (Google Sheets)")
                except Exception as e:
                    bot_logger.error(f"Error sending to n8n for entry {entry.id}: {e}")

            # Clear FSM state
            await state.clear()

            # Notify admin
            await callback.message.edit_text(
                f"✅ <b>Отчёт отправлен в группу!</b>\n\n"
                f"💬 Сообщение опубликовано в групповом чате.\n"
                f"📊 Work journal и Google Sheets обновлены.",
                reply_markup=get_back_to_main_menu_keyboard(),
                parse_mode="HTML"
            )
            await callback.answer("✅ Отправлено в группу")

    except Exception as e:
        bot_logger.error(f"❌ Error in send_to_group callback: {e}")
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

            # Escape HTML
            title_escaped = task_report.task_title.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

            await callback.message.edit_text(
                f"✅ <b>Задача закрыта без отчёта клиенту</b>\n\n"
                f"<b>Задача:</b> #{task_report.plane_sequence_id}\n"
                f"<b>Название:</b> {title_escaped}\n\n"
                f"{client_status}\n\n"
                f"📝 Задача завершена, отчёт сохранён в базе данных.",
                reply_markup=get_back_to_main_menu_keyboard(),
                parse_mode="HTML"
            )

            # Clear state
            await state.clear()
            await callback.answer()

    except Exception as e:
        bot_logger.error(f"❌ Error in close_no_report callback: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)
