"""
Task Reports Voice Fill Handler

Голосовое заполнение отчёта с детекцией конфликтов между данными из Plane и голоса.

Flow:
1. Admin в состоянии filling_report отправляет голосовое
2. Бот транскрибирует + AI извлекает данные
3. Сравнивает с данными из Plane (project_name, assignees)
4. Если есть конфликты → показывает UI выбора
5. Если нет → автозаполняет и переходит к preview
"""

import json
from typing import Optional, Dict, List, Any, Tuple
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ..states import TaskReportStates
from ....config import settings
from ....database.database import get_async_session
from ....services.task_reports_service import task_reports_service
from ....utils.logger import bot_logger
from ....handlers.voice_transcription import (
    download_voice_file,
    transcribe_with_whisper,
    extract_report_data_with_ai,
    get_valid_companies_and_workers
)


router = Router(name="task_reports_voice_fill")

# Temporary storage for conflict resolution
_conflict_cache: Dict[str, Dict] = {}


def detect_conflicts(
    voice_data: Dict[str, Any],
    plane_data: Dict[str, Any]
) -> Dict[str, Dict[str, Any]]:
    """
    Detect conflicts between voice-extracted data and Plane data.

    Returns dict of conflicts:
    {
        "company": {"voice": "Харизма", "plane": "Харц Лабз"},
        "workers": {"voice": ["Костя"], "plane": ["Дима", "Тимофей"]},
        ...
    }
    """
    conflicts = {}

    # Check company
    voice_company = voice_data.get("company", "")
    plane_company = plane_data.get("plane_project_name", "")

    if voice_company and plane_company:
        # Normalize for comparison (lowercase, strip)
        v_norm = voice_company.lower().strip()
        p_norm = plane_company.lower().strip()

        # Check if they're different (and not substrings of each other)
        if v_norm != p_norm and v_norm not in p_norm and p_norm not in v_norm:
            conflicts["company"] = {
                "voice": voice_company,
                "plane": plane_company
            }

    # Check workers
    voice_workers = voice_data.get("workers", [])
    plane_assignees = plane_data.get("plane_assignees", [])

    if voice_workers and plane_assignees:
        # Normalize for comparison
        v_set = set(w.lower().strip() for w in voice_workers)
        p_set = set(w.lower().strip() for w in plane_assignees)

        # If sets are different (not just added workers)
        if v_set != p_set and not v_set.issubset(p_set) and not p_set.issubset(v_set):
            conflicts["workers"] = {
                "voice": voice_workers,
                "plane": plane_assignees
            }

    return conflicts


def create_conflict_resolution_keyboard(
    task_report_id: int,
    conflicts: Dict[str, Dict[str, Any]]
) -> InlineKeyboardMarkup:
    """Create keyboard for resolving conflicts"""
    builder = InlineKeyboardBuilder()

    for field, values in conflicts.items():
        voice_val = values["voice"]
        plane_val = values["plane"]

        # Format display values
        if isinstance(voice_val, list):
            voice_display = ", ".join(voice_val[:3])
            if len(voice_val) > 3:
                voice_display += "..."
        else:
            voice_display = str(voice_val)[:30]

        if isinstance(plane_val, list):
            plane_display = ", ".join(plane_val[:3])
            if len(plane_val) > 3:
                plane_display += "..."
        else:
            plane_display = str(plane_val)[:30]

        field_emoji = "🏢" if field == "company" else "👥"
        field_name = "Компания" if field == "company" else "Исполнители"

        # Header
        builder.row(InlineKeyboardButton(
            text=f"── {field_emoji} {field_name} ──",
            callback_data="noop"
        ))

        # Voice option
        builder.row(InlineKeyboardButton(
            text=f"🎤 {voice_display}",
            callback_data=f"resolve_conflict:{task_report_id}:{field}:voice"
        ))

        # Plane option
        builder.row(InlineKeyboardButton(
            text=f"✈️ {plane_display}",
            callback_data=f"resolve_conflict:{task_report_id}:{field}:plane"
        ))

    # Actions
    builder.row(
        InlineKeyboardButton(
            text="✅ Применить выбор",
            callback_data=f"apply_voice_fill:{task_report_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data=f"cancel_voice_fill:{task_report_id}"
        )
    )

    return builder.as_markup()


def create_no_conflict_keyboard(task_report_id: int) -> InlineKeyboardMarkup:
    """Keyboard when no conflicts - just confirm"""
    builder = InlineKeyboardBuilder()

    builder.row(InlineKeyboardButton(
        text="✅ Применить и продолжить",
        callback_data=f"apply_voice_fill:{task_report_id}"
    ))
    builder.row(InlineKeyboardButton(
        text="✏️ Редактировать вручную",
        callback_data=f"edit_report:{task_report_id}"
    ))
    builder.row(InlineKeyboardButton(
        text="❌ Отмена",
        callback_data=f"cancel_voice_fill:{task_report_id}"
    ))

    return builder.as_markup()


@router.message(StateFilter(TaskReportStates.filling_report), F.voice)
async def handle_voice_in_report_state(message: Message, bot: Bot, state: FSMContext):
    """
    Handle voice message when admin is filling a task report.

    This allows admin to fill report with voice instead of typing.
    """
    user_id = message.from_user.id

    # Check if admin
    if not settings.is_admin(user_id):
        return

    # Get state data
    state_data = await state.get_data()
    task_report_id = state_data.get("task_report_id")

    if not task_report_id:
        await message.reply("❌ Ошибка: ID отчёта не найден")
        await state.clear()
        return

    # Check if transcription is available
    has_whisper = bool(getattr(settings, 'huggingface_api_key', None) or
                       getattr(settings, 'groq_api_key', None) or
                       getattr(settings, 'openai_api_key', None))
    has_openrouter = bool(getattr(settings, 'openrouter_api_key', None))

    if not has_whisper:
        await message.reply(
            "⚠️ Голосовое заполнение недоступно\n"
            "Настройте HUGGINGFACE_API_KEY в .env",
            parse_mode=None
        )
        return

    # Show processing status
    status_msg = await message.reply(
        "🎤 <b>Голосовое заполнение отчёта</b>\n\n"
        "⏳ Обрабатываю...",
        parse_mode="HTML"
    )

    try:
        # 1. Download and transcribe
        file_path = await download_voice_file(bot, message.voice.file_id)
        if not file_path:
            await status_msg.edit_text("❌ Не удалось скачать голосовое")
            return

        await status_msg.edit_text(
            "🎤 <b>Голосовое заполнение отчёта</b>\n\n"
            "⏳ Транскрибирую...",
            parse_mode="HTML"
        )

        transcription = await transcribe_with_whisper(file_path)
        if not transcription:
            await status_msg.edit_text("❌ Не удалось транскрибировать")
            return

        # 2. Extract data with AI (if available)
        voice_data = {}
        if has_openrouter:
            await status_msg.edit_text(
                "🎤 <b>Голосовое заполнение отчёта</b>\n\n"
                f"✅ Транскрипция:\n<i>{transcription[:150]}...</i>\n\n"
                "⏳ AI извлекает данные...",
                parse_mode="HTML"
            )

            extraction = await extract_report_data_with_ai(transcription)
            if extraction:
                # Get first entry (for single report)
                entries = extraction.get("entries", [])
                if entries:
                    voice_data = entries[0]
                elif extraction.get("work_duration"):
                    voice_data = extraction

        # 3. Get Plane data from FSM state
        plane_data = {
            "plane_project_name": state_data.get("plane_project_name"),
            "plane_assignees": state_data.get("plane_assignees", []),
            "plane_closed_by": state_data.get("plane_closed_by")
        }

        # 4. Get task report for additional context
        async for session in get_async_session():
            task_report = await task_reports_service.get_task_report(session, task_report_id)
            if not task_report:
                await status_msg.edit_text("❌ Отчёт не найден")
                return

        # 5. Detect conflicts
        conflicts = {}
        if voice_data:
            conflicts = detect_conflicts(voice_data, plane_data)

        # 6. Store data for later application
        cache_key = f"voice_fill:{user_id}:{task_report_id}"
        _conflict_cache[cache_key] = {
            "transcription": transcription,
            "voice_data": voice_data,
            "plane_data": plane_data,
            "conflicts": conflicts,
            "resolved": {},  # Will store user's choices
            "task_report_id": task_report_id
        }

        # 7. Show result with conflicts or confirmation
        if conflicts:
            # Show conflict resolution UI
            conflict_text = "⚠️ <b>Обнаружены расхождения:</b>\n\n"

            for field, values in conflicts.items():
                field_name = "Компания" if field == "company" else "Исполнители"
                field_emoji = "🏢" if field == "company" else "👥"

                v_val = values["voice"]
                p_val = values["plane"]

                if isinstance(v_val, list):
                    v_str = ", ".join(v_val)
                else:
                    v_str = str(v_val)

                if isinstance(p_val, list):
                    p_str = ", ".join(p_val)
                else:
                    p_str = str(p_val)

                conflict_text += (
                    f"{field_emoji} <b>{field_name}:</b>\n"
                    f"  🎤 Голос: {v_str}\n"
                    f"  ✈️ Plane: {p_str}\n\n"
                )

            conflict_text += "<i>Выберите какие данные использовать:</i>"

            # Format extracted data
            data_preview = _format_voice_data_preview(voice_data, transcription)

            await status_msg.edit_text(
                f"🎤 <b>Голосовое заполнение отчёта #{task_report.plane_sequence_id}</b>\n\n"
                f"<b>📝 Транскрипция:</b>\n"
                f"<i>{transcription[:200]}{'...' if len(transcription) > 200 else ''}</i>\n\n"
                f"{data_preview}\n\n"
                f"{conflict_text}",
                parse_mode="HTML",
                reply_markup=create_conflict_resolution_keyboard(task_report_id, conflicts)
            )
        else:
            # No conflicts - show confirmation
            data_preview = _format_voice_data_preview(voice_data, transcription)

            await status_msg.edit_text(
                f"🎤 <b>Голосовое заполнение отчёта #{task_report.plane_sequence_id}</b>\n\n"
                f"<b>📝 Транскрипция:</b>\n"
                f"<i>{transcription[:200]}{'...' if len(transcription) > 200 else ''}</i>\n\n"
                f"{data_preview}\n\n"
                f"✅ <b>Конфликтов не обнаружено!</b>\n"
                f"Данные будут объединены с информацией из Plane.",
                parse_mode="HTML",
                reply_markup=create_no_conflict_keyboard(task_report_id)
            )

        bot_logger.info(
            f"Voice fill for report #{task_report_id}",
            extra={
                "user_id": user_id,
                "has_conflicts": bool(conflicts),
                "conflicts_count": len(conflicts)
            }
        )

    except Exception as e:
        bot_logger.error(f"Error in voice fill: {e}")
        await status_msg.edit_text(f"❌ Ошибка: {str(e)[:100]}")


def _format_voice_data_preview(voice_data: Dict, transcription: str) -> str:
    """Format extracted voice data for display"""
    if not voice_data:
        return "<b>⚠️ AI не смог извлечь структурированные данные</b>\nТекст будет использован как описание работы."

    lines = ["<b>📊 Извлечённые данные:</b>"]

    if voice_data.get("work_duration"):
        lines.append(f"⏱️ Длительность: {voice_data['work_duration']}")

    if voice_data.get("is_travel") is not None:
        travel_str = "✅ Выезд" if voice_data["is_travel"] else "🏠 Удалённо"
        lines.append(f"🚗 Тип: {travel_str}")

    if voice_data.get("company"):
        lines.append(f"🏢 Компания: {voice_data['company']}")

    if voice_data.get("workers"):
        workers = voice_data["workers"]
        if isinstance(workers, list):
            workers_str = ", ".join(workers)
        else:
            workers_str = str(workers)
        lines.append(f"👥 Исполнители: {workers_str}")

    if voice_data.get("work_description"):
        desc = voice_data["work_description"][:100]
        if len(voice_data["work_description"]) > 100:
            desc += "..."
        lines.append(f"📝 Описание: {desc}")

    return "\n".join(lines)


@router.callback_query(F.data.startswith("resolve_conflict:"))
async def handle_resolve_conflict(callback: CallbackQuery, state: FSMContext):
    """Handle conflict resolution choice"""
    try:
        parts = callback.data.split(":")
        task_report_id = int(parts[1])
        field = parts[2]  # "company" or "workers"
        choice = parts[3]  # "voice" or "plane"

        user_id = callback.from_user.id
        cache_key = f"voice_fill:{user_id}:{task_report_id}"

        cached = _conflict_cache.get(cache_key)
        if not cached:
            await callback.answer("❌ Данные истекли", show_alert=True)
            return

        # Store resolution
        cached["resolved"][field] = choice

        # Update message to show current selections
        conflicts = cached["conflicts"]
        resolved = cached["resolved"]

        selection_text = ""
        for f, values in conflicts.items():
            chosen = resolved.get(f)
            if chosen:
                val = values[chosen]
                if isinstance(val, list):
                    val_str = ", ".join(val)
                else:
                    val_str = str(val)
                source = "🎤 Голос" if chosen == "voice" else "✈️ Plane"
                selection_text += f"✅ {f}: {source} → {val_str}\n"
            else:
                selection_text += f"⏳ {f}: <i>не выбрано</i>\n"

        await callback.answer(f"Выбрано: {'голос' if choice == 'voice' else 'Plane'}")

        # Check if all conflicts resolved
        all_resolved = all(f in resolved for f in conflicts)

        if all_resolved:
            # Update keyboard to enable apply button
            await callback.message.edit_reply_markup(
                reply_markup=create_conflict_resolution_keyboard(task_report_id, conflicts)
            )

    except Exception as e:
        bot_logger.error(f"Error resolving conflict: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("apply_voice_fill:"))
async def handle_apply_voice_fill(callback: CallbackQuery, state: FSMContext):
    """Apply voice-extracted data to task report"""
    try:
        task_report_id = int(callback.data.split(":")[1])
        user_id = callback.from_user.id

        cache_key = f"voice_fill:{user_id}:{task_report_id}"
        cached = _conflict_cache.get(cache_key)

        if not cached:
            await callback.answer("❌ Данные истекли", show_alert=True)
            return

        voice_data = cached["voice_data"]
        plane_data = cached["plane_data"]
        conflicts = cached["conflicts"]
        resolved = cached["resolved"]
        transcription = cached["transcription"]

        # Build final data by merging voice + plane + resolved conflicts
        final_data = {}

        # Report text (always from voice)
        final_data["report_text"] = voice_data.get("work_description") or transcription

        # Duration (from voice)
        final_data["work_duration"] = voice_data.get("work_duration")

        # Is travel (from voice)
        final_data["is_travel"] = voice_data.get("is_travel", False)

        # Company - check if conflict was resolved
        if "company" in conflicts:
            choice = resolved.get("company", "plane")  # Default to Plane
            final_data["company"] = conflicts["company"][choice]
        else:
            # No conflict - prefer voice if available, else Plane
            final_data["company"] = voice_data.get("company") or plane_data.get("plane_project_name")

        # Workers - check if conflict was resolved
        if "workers" in conflicts:
            choice = resolved.get("workers", "plane")  # Default to Plane
            final_data["workers"] = conflicts["workers"][choice]
        else:
            # No conflict - prefer voice if available, else Plane
            final_data["workers"] = voice_data.get("workers") or plane_data.get("plane_assignees")

        # Apply to database
        async for session in get_async_session():
            task_report = await task_reports_service.get_task_report(session, task_report_id)

            if not task_report:
                await callback.answer("❌ Отчёт не найден", show_alert=True)
                return

            # Update report text
            if final_data["report_text"]:
                task_report.report_text = final_data["report_text"]

            # Update metadata
            if final_data["work_duration"]:
                task_report.work_duration = final_data["work_duration"]

            if final_data["is_travel"] is not None:
                task_report.is_travel = final_data["is_travel"]

            if final_data["company"]:
                task_report.company = final_data["company"]

            if final_data["workers"]:
                if isinstance(final_data["workers"], list):
                    task_report.workers = json.dumps(final_data["workers"], ensure_ascii=False)
                else:
                    task_report.workers = final_data["workers"]

            task_report.submitted_by_telegram_id = user_id

            await session.commit()
            await session.refresh(task_report)

            bot_logger.info(
                f"Voice fill applied to report #{task_report_id}",
                extra={
                    "user_id": user_id,
                    "company": final_data["company"],
                    "workers": final_data["workers"]
                }
            )

        # Clean up cache
        del _conflict_cache[cache_key]

        # Move to preview state
        await state.set_state(TaskReportStates.reviewing_report)

        # Show preview
        from .preview import callback_preview_report

        # Create fake callback for preview handler
        callback.data = f"preview_report:{task_report_id}"
        await callback_preview_report(callback)

    except Exception as e:
        bot_logger.error(f"Error applying voice fill: {e}")
        await callback.answer("❌ Ошибка применения данных", show_alert=True)


@router.callback_query(F.data.startswith("cancel_voice_fill:"))
async def handle_cancel_voice_fill(callback: CallbackQuery, state: FSMContext):
    """Cancel voice fill and return to manual input"""
    try:
        task_report_id = int(callback.data.split(":")[1])
        user_id = callback.from_user.id

        # Clean up cache
        cache_key = f"voice_fill:{user_id}:{task_report_id}"
        if cache_key in _conflict_cache:
            del _conflict_cache[cache_key]

        await callback.message.edit_text(
            "❌ <b>Голосовое заполнение отменено</b>\n\n"
            "Отправьте текст отчёта вручную или используйте /cancel для отмены.",
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        bot_logger.error(f"Error cancelling voice fill: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data == "noop")
async def handle_noop(callback: CallbackQuery):
    """Handle noop callbacks (section headers)"""
    await callback.answer()
