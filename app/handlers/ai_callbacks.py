"""
AI Callback Handlers

Обработка callback кнопок для:
1. Подтверждение/отклонение AI-детектированных задач
2. Выбор задачи для голосового отчёта
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from ..utils.logger import bot_logger
from ..config import settings
from ..integrations.plane import plane_api
from ..services.redis_service import redis_service
from .ai_edit_states import AIEditTaskStates

router = Router(name="ai_callbacks")


# ==================== TASK DETECTION CALLBACKS ====================

@router.callback_query(F.data.startswith("ai_confirm_task:"))
async def callback_ai_confirm_task(callback: CallbackQuery):
    """
    Подтверждение создания задачи в Plane — с dedup check.

    callback_data: ai_confirm_task:{chat_id}:{message_id}
    """
    try:
        parts = callback.data.split(":")
        chat_id = int(parts[1])
        message_id = int(parts[2])

        cache_key = f"ai_task:{chat_id}:{message_id}"
        cached = await redis_service.get_json(cache_key)

        if not cached:
            await callback.answer("❌ Данные истекли. Попробуйте снова.", show_alert=True)
            return

        task_data = cached.get('task_data', {})
        plane = cached.get('plane', {})
        project_id = plane.get('project_id')
        title = task_data.get('title', 'Задача из чата')

        # --- Dedup: search for similar open issues ---
        if project_id:
            similar = await plane_api.search_issues(project_id, title, limit=3)
            if similar:
                # Show dedup options instead of creating
                buttons = []
                for s in similar:
                    label = f"📎 #{s['sequence_id']} {s['name'][:35]}"
                    buttons.append([InlineKeyboardButton(
                        text=label,
                        callback_data=f"ai_add_comment:{chat_id}:{message_id}:{s['id'][:36]}"
                    )])
                buttons.append([InlineKeyboardButton(
                    text="➕ Создать новую задачу",
                    callback_data=f"ai_force_create:{chat_id}:{message_id}"
                )])
                buttons.append([InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=f"ai_reject_task:{chat_id}:{message_id}"
                )])

                await callback.message.edit_text(
                    f"🔍 <b>Найдены похожие задачи</b>\n\n"
                    f"📝 Новая: <b>{title}</b>\n\n"
                    + "\n".join(
                        f"• #{s['sequence_id']} {s['name']} "
                        f"({s.get('state_name', '?')})"
                        for s in similar
                    )
                    + "\n\n<i>Добавить коммент к существующей или создать новую?</i>",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
                )
                await callback.answer()
                return

        # No duplicates found — create directly
        await _create_plane_issue(callback, cache_key, cached)

    except Exception as e:
        bot_logger.error(f"Error in ai_confirm_task callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("ai_force_create:"))
async def callback_ai_force_create(callback: CallbackQuery):
    """Force create task after dedup check showed similar issues."""
    try:
        parts = callback.data.split(":")
        chat_id = int(parts[1])
        message_id = int(parts[2])
        cache_key = f"ai_task:{chat_id}:{message_id}"
        cached = await redis_service.get_json(cache_key)

        if not cached:
            await callback.answer("❌ Данные истекли", show_alert=True)
            return

        await _create_plane_issue(callback, cache_key, cached)

    except Exception as e:
        bot_logger.error(f"Error in ai_force_create: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("ai_add_comment:"))
async def callback_ai_add_comment(callback: CallbackQuery):
    """Add comment to existing issue instead of creating a new one."""
    try:
        parts = callback.data.split(":")
        chat_id = int(parts[1])
        message_id = int(parts[2])
        issue_id = parts[3]

        cache_key = f"ai_task:{chat_id}:{message_id}"
        cached = await redis_service.get_json(cache_key)

        if not cached:
            await callback.answer("❌ Данные истекли", show_alert=True)
            return

        task_data = cached.get('task_data', {})
        original = cached.get('original', {})
        plane = cached.get('plane', {})
        project_id = plane.get('project_id')

        comment_html = (
            f"<p><strong>Новое сообщение из чата:</strong></p>"
            f"<p>{task_data.get('description', original.get('text', ''))}</p>"
            f"<p><em>— {original.get('user_name', 'Unknown')}</em></p>"
        )

        result = await plane_api.create_issue_comment(
            project_id=project_id,
            issue_id=issue_id,
            comment=comment_html
        )

        if result:
            await callback.message.edit_text(
                f"💬 <b>Комментарий добавлен к задаче</b>\n\n"
                f"<a href=\"https://plane.hhivp.com/{settings.plane_workspace_slug}/projects/{project_id}/issues/{issue_id}\">Открыть в Plane</a>",
                parse_mode="HTML"
            )
            bot_logger.info(f"AI task added as comment to issue {issue_id[:8]}")
        else:
            await callback.message.edit_text(
                "❌ <b>Ошибка добавления комментария</b>",
                parse_mode="HTML"
            )

        await redis_service.delete(cache_key)
        await callback.answer()

    except Exception as e:
        bot_logger.error(f"Error in ai_add_comment: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


async def _create_plane_issue(callback: CallbackQuery, cache_key: str, cached: dict):
    """Helper: create issue in Plane and respond."""
    task_data = cached.get('task_data', {})
    plane = cached.get('plane', {})
    original = cached.get('original', {})
    title = task_data.get('title', 'Задача из чата')

    await callback.message.edit_text(
        f"⏳ <b>Создаю задачу в Plane...</b>\n\n📝 {title}",
        parse_mode="HTML"
    )

    try:
        description = (
            f"<p><strong>Автоматически создано из сообщения в чате</strong></p>"
            f"<p>{task_data.get('description', '')}</p>"
            f"<hr/>"
            f"<p><em>Автор: {original.get('user_name', 'Unknown')}</em></p>"
        )

        issue = await plane_api.create_issue(
            project_id=plane.get('project_id'),
            name=title,
            description=description,
            priority=task_data.get('priority', 'medium')
        )

        if issue:
            seq_id = issue.get('sequence_id', '?')
            await callback.message.edit_text(
                f"✅ <b>Задача создана!</b>\n\n"
                f"📝 <b>{title}</b>\n"
                f"🔢 Номер: #{seq_id}\n"
                f"📊 Проект: {plane.get('project_name', 'N/A')}\n\n"
                f"<a href=\"https://plane.hhivp.com/{settings.plane_workspace_slug}/projects/{plane.get('project_id')}/issues/{issue.get('id')}\">Открыть в Plane</a>",
                parse_mode="HTML"
            )
            bot_logger.info(f"AI task created: #{seq_id}")
        else:
            await callback.message.edit_text(
                "❌ <b>Ошибка создания задачи</b>",
                parse_mode="HTML"
            )
    except Exception as e:
        bot_logger.error(f"Error creating Plane issue: {e}")
        await callback.message.edit_text(
            f"❌ <b>Ошибка:</b> {e}",
            parse_mode="HTML"
        )

    await redis_service.delete(cache_key)
    await callback.answer()


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
        cache_key = f"ai_task:{chat_id}:{message_id}"
        await redis_service.delete(cache_key)

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
    Start editing AI-detected task before creation.

    callback_data: ai_edit_task:{chat_id}:{message_id}
    """
    try:
        parts = callback.data.split(":")
        chat_id = int(parts[1])
        message_id = int(parts[2])

        cache_key = f"ai_task:{chat_id}:{message_id}"
        cached = await redis_service.get_json(cache_key)

        if not cached:
            await callback.answer("❌ Данные истекли", show_alert=True)
            return

        task_data = cached.get('task_data', {})
        title = task_data.get('title', 'Без названия')

        # Save cache_key in FSM state for later steps
        await state.update_data(ai_edit_cache_key=cache_key)
        await state.set_state(AIEditTaskStates.editing_title)

        skip_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Оставить как есть", callback_data="ai_edit_skip_title")]
        ])

        await callback.message.edit_text(
            f"✏️ <b>Редактирование задачи</b>\n\n"
            f"📝 <b>Текущее название:</b>\n<code>{title}</code>\n\n"
            f"Отправьте новое название или нажмите кнопку, чтобы оставить:",
            parse_mode="HTML",
            reply_markup=skip_kb
        )

        await callback.answer()

    except Exception as e:
        bot_logger.error(f"Error in ai_edit_task callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data == "ai_edit_skip_title", AIEditTaskStates.editing_title)
async def callback_ai_edit_skip_title(callback: CallbackQuery, state: FSMContext):
    """Skip title editing, move to description."""
    await _show_description_step(callback.message, state, callback)


@router.message(AIEditTaskStates.editing_title)
async def handle_ai_edit_title(message: Message, state: FSMContext):
    """Receive new title from user."""
    await state.update_data(new_title=message.text.strip())
    await _show_description_step(message, state)


async def _show_description_step(msg, state: FSMContext, callback=None):
    """Show description editing step."""
    data = await state.get_data()
    cache_key = data.get('ai_edit_cache_key')
    cached = await redis_service.get_json(cache_key)

    if not cached:
        text = "❌ Данные истекли. Попробуйте снова."
        if callback:
            await msg.edit_text(text, parse_mode="HTML")
            await callback.answer()
        else:
            await msg.answer(text, parse_mode="HTML")
        await state.clear()
        return

    task_data = cached.get('task_data', {})
    description = task_data.get('description', 'Нет описания')

    await state.set_state(AIEditTaskStates.editing_description)

    skip_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Оставить как есть", callback_data="ai_edit_skip_desc")]
    ])

    text = (
        f"✏️ <b>Описание задачи</b>\n\n"
        f"<i>{description[:500]}</i>\n\n"
        f"Отправьте новое описание или нажмите кнопку:"
    )

    if callback:
        await msg.edit_text(text, parse_mode="HTML", reply_markup=skip_kb)
        await callback.answer()
    else:
        await msg.answer(text, parse_mode="HTML", reply_markup=skip_kb)


@router.callback_query(F.data == "ai_edit_skip_desc", AIEditTaskStates.editing_description)
async def callback_ai_edit_skip_desc(callback: CallbackQuery, state: FSMContext):
    """Skip description editing, show preview."""
    await _show_edit_preview(callback.message, state, callback)


@router.message(AIEditTaskStates.editing_description)
async def handle_ai_edit_description(message: Message, state: FSMContext):
    """Receive new description from user."""
    await state.update_data(new_description=message.text.strip())
    await _show_edit_preview(message, state)


async def _show_edit_preview(msg, state: FSMContext, callback=None):
    """Show preview of edited task with confirm/cancel buttons."""
    data = await state.get_data()
    cache_key = data.get('ai_edit_cache_key')
    cached = await redis_service.get_json(cache_key)

    if not cached:
        text = "❌ Данные истекли. Попробуйте снова."
        if callback:
            await msg.edit_text(text, parse_mode="HTML")
            await callback.answer()
        else:
            await msg.answer(text, parse_mode="HTML")
        await state.clear()
        return

    task_data = cached.get('task_data', {})
    title = data.get('new_title', task_data.get('title', 'Без названия'))
    description = data.get('new_description', task_data.get('description', ''))
    priority = task_data.get('priority', 'medium')

    await state.set_state(AIEditTaskStates.confirming)

    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Создать", callback_data="ai_edit_confirm"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="ai_edit_cancel"),
        ]
    ])

    text = (
        f"📋 <b>Предпросмотр задачи</b>\n\n"
        f"📝 <b>Название:</b> {title}\n"
        f"🎯 <b>Приоритет:</b> {priority}\n\n"
        f"📄 <b>Описание:</b>\n<i>{description[:300]}</i>\n\n"
        f"Создать задачу в Plane?"
    )

    if callback:
        await msg.edit_text(text, parse_mode="HTML", reply_markup=confirm_kb)
        await callback.answer()
    else:
        await msg.answer(text, parse_mode="HTML", reply_markup=confirm_kb)


@router.callback_query(F.data == "ai_edit_confirm", AIEditTaskStates.confirming)
async def callback_ai_edit_confirm(callback: CallbackQuery, state: FSMContext):
    """Create task in Plane with edited data."""
    try:
        data = await state.get_data()
        cache_key = data.get('ai_edit_cache_key')
        cached = await redis_service.get_json(cache_key)

        if not cached:
            await callback.answer("❌ Данные истекли", show_alert=True)
            await state.clear()
            return

        task_data = cached.get('task_data', {})
        plane = cached.get('plane', {})
        original = cached.get('original', {})

        title = data.get('new_title', task_data.get('title', 'Задача из чата'))
        description_text = data.get('new_description', task_data.get('description', ''))
        priority = task_data.get('priority', 'medium')

        await callback.message.edit_text(
            f"⏳ <b>Создаю задачу в Plane...</b>\n\n📝 {title}",
            parse_mode="HTML"
        )

        description = (
            f"<p><strong>Автоматически создано из сообщения в чате</strong></p>"
            f"<p>{description_text}</p>"
            f"<hr/>"
            f"<p><em>Автор: {original.get('user_name', 'Unknown')}</em></p>"
            f"<p><em>Telegram User ID: {original.get('user_id')}</em></p>"
        )

        issue = await plane_api.create_issue(
            project_id=plane.get('project_id'),
            name=title,
            description=description,
            priority=priority
        )

        if issue:
            seq_id = issue.get('sequence_id', '?')
            await callback.message.edit_text(
                f"✅ <b>Задача создана!</b>\n\n"
                f"📝 <b>{title}</b>\n"
                f"🔢 Номер: #{seq_id}\n"
                f"📊 Проект: {plane.get('project_name', 'N/A')}\n\n"
                f"<a href=\"https://plane.hhivp.com/{settings.plane_workspace_slug}/projects/{plane.get('project_id')}/issues/{issue.get('id')}\">Открыть в Plane</a>",
                parse_mode="HTML"
            )
            bot_logger.info(f"AI task edited and created: #{seq_id}")
        else:
            await callback.message.edit_text(
                "❌ <b>Ошибка создания задачи</b>",
                parse_mode="HTML"
            )

        await redis_service.delete(cache_key)
        await state.clear()
        await callback.answer()

    except Exception as e:
        bot_logger.error(f"Error in ai_edit_confirm: {e}")
        await state.clear()
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data == "ai_edit_cancel", AIEditTaskStates.confirming)
async def callback_ai_edit_cancel(callback: CallbackQuery, state: FSMContext):
    """Cancel task editing."""
    data = await state.get_data()
    cache_key = data.get('ai_edit_cache_key')
    if cache_key:
        await redis_service.delete(cache_key)

    await state.clear()
    await callback.message.edit_text(
        "❌ <b>Создание задачи отменено</b>",
        parse_mode="HTML"
    )
    await callback.answer("Отменено")


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
        cache_key = f"voice_task_select:{admin_id}:{message_id}"
        cached = await redis_service.get_json(cache_key)

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
        await redis_service.delete(cache_key)

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
        cache_key = f"voice_task_select:{admin_id}:{message_id}"
        cached = await redis_service.get_json(cache_key)

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
        cache_key = f"voice_task_select:{admin_id}:{message_id}"
        await redis_service.delete(cache_key)

        await callback.message.edit_text(
            "❌ <b>Голосовой отчёт отменён</b>",
            parse_mode="HTML"
        )

        await callback.answer("Отменено")

    except Exception as e:
        bot_logger.error(f"Error in voice_cancel callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)
