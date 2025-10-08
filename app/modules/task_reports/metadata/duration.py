"""
Task Reports Metadata - Duration Handlers

Duration selection handlers with quick buttons and custom input
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
import re

from ..states import TaskReportStates
from ..keyboards import create_duration_keyboard, create_work_type_keyboard
from ..utils import parse_report_id_safely
from ....database.database import get_async_session
from ....services.task_reports_service import task_reports_service
from ....utils.logger import bot_logger


router = Router(name="task_reports_duration")


# ═══════════════════════════════════════════════════════════
# DURATION SELECTION
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
