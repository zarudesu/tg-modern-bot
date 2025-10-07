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
from ...utils.logger import bot_logger
from ...config import settings


router = Router(name="task_reports_handlers")


# ═══════════════════════════════════════════════════════════
# CALLBACK: START FILLING REPORT
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("fill_report:"))
async def callback_fill_report(callback: CallbackQuery, state: FSMContext):
    """
    Admin clicks "Fill Report" button from notification

    Callback data format: fill_report:{task_report_id}
    """
    try:
        task_report_id = int(callback.data.split(":")[1])
        bot_logger.info(f"📝 Admin {callback.from_user.id} started filling report #{task_report_id}")

        # Get task report from DB
        async for session in get_async_session():
            task_report = await task_reports_service.get_task_report(session, task_report_id)

            if not task_report:
                await callback.answer("❌ Отчёт не найден", show_alert=True)
                return

            # Set FSM state
            await state.set_state(TaskReportStates.filling_report)
            await state.update_data(task_report_id=task_report_id)

            # Show autofilled text if available
            if task_report.report_text:
                preview_text = task_report.report_text[:500]
                if len(task_report.report_text) > 500:
                    preview_text += "..."

                autofill_notice = ""
                if task_report.auto_filled_from_journal:
                    autofill_notice = "\\n\\n✅ _Автоматически заполнено из work journal_"

                await callback.message.edit_text(
                    f"📝 **Заполнение отчёта для задачи #{task_report.plane_sequence_id}**\\n\\n"
                    f"**Текущий текст отчёта:**\\n{preview_text}{autofill_notice}\\n\\n"
                    f"Отправьте новый текст отчёта или используйте кнопки ниже:",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(
                            text="✅ Оставить как есть",
                            callback_data=f"approve_report:{task_report_id}"
                        )],
                        [InlineKeyboardButton(
                            text="❌ Отменить",
                            callback_data=f"cancel_report:{task_report_id}"
                        )]
                    ])
                )
            else:
                # No autofill - ask admin to write report
                await callback.message.edit_text(
                    f"📝 **Заполнение отчёта для задачи #{task_report.plane_sequence_id}**\\n\\n"
                    f"**Название задачи:** {task_report.task_title}\\n\\n"
                    f"Напишите отчёт о выполненной работе для клиента:",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(
                            text="❌ Отменить",
                            callback_data=f"cancel_report:{task_report_id}"
                        )]
                    ])
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
                "❌ Отчёт слишком короткий (минимум 10 символов).\\n\\n"
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

            # Move to review state
            await state.set_state(TaskReportStates.reviewing_report)

            # Show review message
            preview = report_text[:1000]
            if len(report_text) > 1000:
                preview += "..."

            await message.reply(
                f"✅ **Отчёт сохранён!**\\n\\n"
                f"**Задача:** #{task_report.plane_sequence_id}\\n"
                f"**Текст отчёта:**\\n\\n{preview}\\n\\n"
                f"Проверьте и подтвердите отправку клиенту:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="✅ Отправить клиенту",
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
        task_report_id = int(callback.data.split(":")[1])

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
                f"✅ **Отчёт одобрен!**\\n\\n"
                f"**Задача:** #{task_report.plane_sequence_id}\\n\\n"
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
        task_report_id = int(callback.data.split(":")[1])

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
                    f"✅ **Ваша заявка #{task_report.plane_sequence_id} выполнена!**\\n\\n"
                    f"**Название:** {task_report.task_title}\\n\\n"
                    f"**Отчёт о выполненной работе:**\\n\\n{task_report.report_text}"
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
                await callback.message.edit_text(
                    f"✅ **Отчёт отправлен клиенту!**\\n\\n"
                    f"Задача #{task_report.plane_sequence_id} завершена.",
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
    Admin wants to edit report text
    """
    try:
        task_report_id = int(callback.data.split(":")[1])

        # Return to filling state
        await state.set_state(TaskReportStates.filling_report)
        await state.update_data(task_report_id=task_report_id)

        await callback.message.edit_text(
            "✏️ **Редактирование отчёта**\\n\\n"
            "Отправьте новый текст отчёта:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="❌ Отменить",
                    callback_data=f"cancel_report:{task_report_id}"
                )]
            ])
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
        task_report_id = int(callback.data.split(":")[1])

        bot_logger.info(f"❌ Admin {callback.from_user.id} cancelled report #{task_report_id}")

        await callback.message.edit_text(
            "❌ Заполнение отчёта отменено.\\n\\n"
            "Напоминание будет отправлено позже.",
            parse_mode="Markdown"
        )

        # Clear FSM state
        await state.clear()

        await callback.answer()

    except Exception as e:
        bot_logger.error(f"❌ Error in cancel_report callback: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


# ═══════════════════════════════════════════════════════════
# CALLBACK: SKIP REPORT (TODO - disabled for now)
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("skip_report:"))
async def callback_skip_report(callback: CallbackQuery):
    """
    DISABLED: Auto-generate report from work_journal and send immediately

    TODO: Implement in future version
    """
    await callback.answer(
        "🚧 Эта функция пока не реализована.\\n\\n"
        "Пожалуйста, заполните отчёт вручную.",
        show_alert=True
    )
