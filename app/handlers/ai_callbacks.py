"""
AI Callback Handlers

Обработка callback кнопок для:
1. Подтверждение/отклонение AI-детектированных задач
2. Выбор задачи для голосового отчёта
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from ..utils.logger import bot_logger
from ..config import settings
from ..integrations.plane import plane_api

router = Router(name="ai_callbacks")


# ==================== TASK DETECTION CALLBACKS ====================

@router.callback_query(F.data.startswith("ai_confirm_task:"))
async def callback_ai_confirm_task(callback: CallbackQuery):
    """
    Подтверждение создания задачи в Plane.

    callback_data: ai_confirm_task:{chat_id}:{message_id}
    """
    try:
        parts = callback.data.split(":")
        chat_id = int(parts[1])
        message_id = int(parts[2])

        # Получаем данные из кэша
        from .voice_transcription import _transcription_cache
        cache_key = f"ai_task:{chat_id}:{message_id}"
        cached = _transcription_cache.get(cache_key)

        if not cached:
            await callback.answer("❌ Данные истекли. Попробуйте снова.", show_alert=True)
            return

        task_data = cached.get('task_data', {})
        plane = cached.get('plane', {})
        original = cached.get('original', {})

        await callback.message.edit_text(
            f"⏳ <b>Создаю задачу в Plane...</b>\n\n"
            f"📝 {task_data.get('title', 'Без названия')}",
            parse_mode="HTML"
        )

        # Создаём задачу в Plane
        try:
            description = f"""
<p><strong>Автоматически создано из сообщения в чате</strong></p>
<p>{task_data.get('description', '')}</p>
<hr/>
<p><em>Автор сообщения: {original.get('user_name', 'Unknown')}</em></p>
<p><em>Telegram User ID: {original.get('user_id')}</em></p>
<p><em>Chat ID: {chat_id}</em></p>
<p><em>Message ID: {message_id}</em></p>
"""
            issue = await plane_api.create_issue(
                project_id=plane.get('project_id'),
                name=task_data.get('title', 'Задача из чата'),
                description=description,
                priority=task_data.get('priority', 'medium')
            )

            if issue:
                seq_id = issue.get('sequence_id', '?')

                await callback.message.edit_text(
                    f"✅ <b>Задача создана!</b>\n\n"
                    f"📝 <b>{task_data.get('title')}</b>\n"
                    f"🔢 Номер: #{seq_id}\n"
                    f"📊 Проект: {plane.get('project_name', 'N/A')}\n\n"
                    f"<a href=\"https://plane.hhivp.com/{settings.plane_workspace_slug}/projects/{plane.get('project_id')}/issues/{issue.get('id')}\">Открыть в Plane</a>",
                    parse_mode="HTML"
                )

                bot_logger.info(
                    f"AI task confirmed and created: #{seq_id}",
                    extra={
                        "chat_id": chat_id,
                        "issue_id": issue.get('id'),
                        "confirmed_by": callback.from_user.id
                    }
                )
            else:
                await callback.message.edit_text(
                    f"❌ <b>Ошибка создания задачи</b>\n\n"
                    f"Попробуйте создать вручную.",
                    parse_mode="HTML"
                )

        except Exception as e:
            bot_logger.error(f"Error creating task from AI confirmation: {e}")
            await callback.message.edit_text(
                f"❌ <b>Ошибка:</b> {e}",
                parse_mode="HTML"
            )

        # Очищаем кэш
        del _transcription_cache[cache_key]
        await callback.answer()

    except Exception as e:
        bot_logger.error(f"Error in ai_confirm_task callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("ai_reject_task:"))
async def callback_ai_reject_task(callback: CallbackQuery):
    """
    Отклонение AI-детектированной задачи.

    callback_data: ai_reject_task:{chat_id}:{message_id}
    """
    try:
        parts = callback.data.split(":")
        chat_id = int(parts[1])
        message_id = int(parts[2])

        # Очищаем кэш
        from .voice_transcription import _transcription_cache
        cache_key = f"ai_task:{chat_id}:{message_id}"
        if cache_key in _transcription_cache:
            del _transcription_cache[cache_key]

        await callback.message.edit_text(
            "❌ <b>Задача не создана</b>\n\n"
            "<i>AI детекция отклонена пользователем</i>",
            parse_mode="HTML"
        )

        bot_logger.info(
            f"AI task rejected by user",
            extra={
                "chat_id": chat_id,
                "message_id": message_id,
                "rejected_by": callback.from_user.id
            }
        )

        await callback.answer("Задача отклонена")

    except Exception as e:
        bot_logger.error(f"Error in ai_reject_task callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("ai_edit_task:"))
async def callback_ai_edit_task(callback: CallbackQuery, state: FSMContext):
    """
    Редактирование AI-детектированной задачи перед созданием.

    callback_data: ai_edit_task:{chat_id}:{message_id}
    """
    try:
        parts = callback.data.split(":")
        chat_id = int(parts[1])
        message_id = int(parts[2])

        # Получаем данные из кэша
        from .voice_transcription import _transcription_cache
        cache_key = f"ai_task:{chat_id}:{message_id}"
        cached = _transcription_cache.get(cache_key)

        if not cached:
            await callback.answer("❌ Данные истекли", show_alert=True)
            return

        task_data = cached.get('task_data', {})

        # TODO: Реализовать FSM для редактирования
        # Пока показываем текущие данные
        await callback.message.edit_text(
            f"✏️ <b>Редактирование задачи</b>\n\n"
            f"📝 <b>Название:</b>\n<code>{task_data.get('title', 'Без названия')}</code>\n\n"
            f"📄 <b>Описание:</b>\n<i>{task_data.get('description', 'Нет описания')[:200]}</i>\n\n"
            f"🎯 <b>Приоритет:</b> {task_data.get('priority', 'medium')}\n\n"
            f"<i>Функция редактирования в разработке.\n"
            f"Создайте задачу как есть или отклоните.</i>",
            parse_mode="HTML"
        )

        await callback.answer("Функция в разработке")

    except Exception as e:
        bot_logger.error(f"Error in ai_edit_task callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


# ==================== VOICE REPORT CALLBACKS ====================

@router.callback_query(F.data.startswith("voice_select:"))
async def callback_voice_select_task(callback: CallbackQuery):
    """
    Выбор задачи для голосового отчёта из кандидатов.

    callback_data: voice_select:{admin_id}:{message_id}:{candidate_index}
    """
    try:
        parts = callback.data.split(":")
        admin_id = int(parts[1])
        message_id = int(parts[2])
        candidate_idx = int(parts[3])

        # Проверяем права
        if callback.from_user.id != admin_id:
            await callback.answer("❌ Это не ваш отчёт", show_alert=True)
            return

        # Получаем данные из кэша
        from .voice_transcription import _transcription_cache
        cache_key = f"voice_task_select:{admin_id}:{message_id}"
        cached = _transcription_cache.get(cache_key)

        if not cached:
            await callback.answer("❌ Данные истекли", show_alert=True)
            return

        candidates = cached.get('candidates', [])
        if candidate_idx >= len(candidates):
            await callback.answer("❌ Недопустимый индекс", show_alert=True)
            return

        selected_task = candidates[candidate_idx]
        extraction = cached.get('extraction', {})

        await callback.message.edit_text(
            f"✅ <b>Задача выбрана</b>\n\n"
            f"📝 #{selected_task.get('sequence_id')} {selected_task.get('title')}\n\n"
            f"⏳ Создаю отчёт...",
            parse_mode="HTML"
        )

        # TODO: Создать отчёт через task_reports_service
        # Пока показываем что выбрано
        await callback.message.edit_text(
            f"✅ <b>Задача выбрана для отчёта</b>\n\n"
            f"📝 <b>Задача:</b> #{selected_task.get('sequence_id')} {selected_task.get('title')}\n"
            f"⏱ <b>Длительность:</b> {extraction.get('duration_hours', 0)} ч\n"
            f"🚗 <b>Дорога:</b> {extraction.get('travel_hours', 0)} ч\n"
            f"👥 <b>Исполнители:</b> {', '.join(extraction.get('workers', []))}\n\n"
            f"<i>Отчёт будет создан в системе Task Reports</i>",
            parse_mode="HTML"
        )

        # Очищаем кэш
        del _transcription_cache[cache_key]

        bot_logger.info(
            f"Voice report task selected: #{selected_task.get('sequence_id')}",
            extra={"admin_id": admin_id}
        )

        await callback.answer()

    except Exception as e:
        bot_logger.error(f"Error in voice_select callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("voice_find_task:"))
async def callback_voice_find_task(callback: CallbackQuery, state: FSMContext):
    """
    Ручной поиск задачи для голосового отчёта.

    callback_data: voice_find_task:{admin_id}:{message_id}
    """
    try:
        parts = callback.data.split(":")
        admin_id = int(parts[1])
        message_id = int(parts[2])

        if callback.from_user.id != admin_id:
            await callback.answer("❌ Это не ваш отчёт", show_alert=True)
            return

        # TODO: Реализовать FSM для поиска задачи
        await callback.message.edit_text(
            f"🔍 <b>Поиск задачи</b>\n\n"
            f"<i>Функция поиска задачи в разработке.\n"
            f"Используйте /task для поиска вручную.</i>",
            parse_mode="HTML"
        )

        await callback.answer("Функция в разработке")

    except Exception as e:
        bot_logger.error(f"Error in voice_find_task callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("voice_new_task:"))
async def callback_voice_new_task(callback: CallbackQuery, state: FSMContext):
    """
    Создание новой задачи из голосового отчёта.

    callback_data: voice_new_task:{admin_id}:{message_id}
    """
    try:
        parts = callback.data.split(":")
        admin_id = int(parts[1])
        message_id = int(parts[2])

        if callback.from_user.id != admin_id:
            await callback.answer("❌ Это не ваш отчёт", show_alert=True)
            return

        # Получаем данные из кэша
        from .voice_transcription import _transcription_cache
        cache_key = f"voice_task_select:{admin_id}:{message_id}"
        cached = _transcription_cache.get(cache_key)

        if not cached:
            await callback.answer("❌ Данные истекли", show_alert=True)
            return

        transcription = cached.get('transcription', '')
        extraction = cached.get('extraction', {})

        # TODO: Реализовать создание задачи через /task команду
        await callback.message.edit_text(
            f"📝 <b>Создание новой задачи</b>\n\n"
            f"🎤 <b>Транскрипция:</b>\n"
            f"<i>{transcription[:200]}{'...' if len(transcription) > 200 else ''}</i>\n\n"
            f"<i>Используйте команду /task для создания задачи вручную.</i>",
            parse_mode="HTML"
        )

        await callback.answer("Используйте /task")

    except Exception as e:
        bot_logger.error(f"Error in voice_new_task callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("voice_cancel:"))
async def callback_voice_cancel(callback: CallbackQuery):
    """
    Отмена голосового отчёта.

    callback_data: voice_cancel:{admin_id}:{message_id}
    """
    try:
        parts = callback.data.split(":")
        admin_id = int(parts[1])
        message_id = int(parts[2])

        if callback.from_user.id != admin_id:
            await callback.answer("❌ Это не ваш отчёт", show_alert=True)
            return

        # Очищаем кэш
        from .voice_transcription import _transcription_cache
        cache_key = f"voice_task_select:{admin_id}:{message_id}"
        if cache_key in _transcription_cache:
            del _transcription_cache[cache_key]

        await callback.message.edit_text(
            "❌ <b>Голосовой отчёт отменён</b>",
            parse_mode="HTML"
        )

        await callback.answer("Отменено")

    except Exception as e:
        bot_logger.error(f"Error in voice_cancel callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)
