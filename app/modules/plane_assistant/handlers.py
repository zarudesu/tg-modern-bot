"""
/plane AI assistant — natural language interface to Plane.so.

AI-first: all user messages are processed by LLM which decides
what data to fetch and how to respond. Optimized for ADHD users.
"""

import json
import re
import os
import tempfile

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from ...config import settings
from ...utils.logger import bot_logger
from ...core.ai.ai_manager import ai_manager
from ...integrations.plane import plane_api
from . import plane_service
from . import context_manager
from .states import PlaneAssistantStates

router = Router(name="plane_assistant")

# Telegram user_id → Plane email mapping
# Add more users as needed
USER_EMAIL_MAP = {
    5765249027: "zarudesu@gmail.com",  # Константин
}
DEFAULT_EMAIL = "zarudesu@gmail.com"


def _get_plane_email(user_id: int) -> str:
    return USER_EMAIL_MAP.get(user_id, DEFAULT_EMAIL)


SYSTEM_PROMPT = """Ты — AI-ассистент для задач в Plane.so. Помоги IT-специалисту с СДВГ.

ПРАВИЛА:
1. КРАТКО и по делу. Длинные тексты парализуют — максимум 5-7 строк.
2. Выделяй ГЛАВНОЕ: "у тебя X срочных, Y просроченных, начни с Z".
3. Будь человечным, не формальным.
4. ОБЯЗАТЕЛЬНО используй <b>жирный</b> для важного, <i>курсив</i> для пояснений.
5. Если нужно действие — СНАЧАЛА напиши что сделаешь, ПОТОМ JSON:
   {"action": "close_issue", "seq_id": 123, "comment": "optional"}
   {"action": "assign_issue", "seq_id": 123, "assignee": "Тимофей"}
   {"action": "comment_issue", "seq_id": 123, "comment": "текст"}
6. Работай ТОЛЬКО с реальными данными ниже.
7. "Чем заняться" → TOP-3 задачи + ПОЧЕМУ именно они.
8. Задачи старше 3 месяцев без обновлений — предложи закрыть или переназначить.

КОНТЕКСТ WORKSPACE:
{workspace_context}

ПРЕДЫДУЩИЙ РАЗГОВОР:
{conversation_history}

ДАННЫЕ ИЗ PLANE:
{plane_data}
"""


def _escape_html(text: str) -> str:
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _extract_action(ai_text: str) -> tuple:
    """Extract JSON action block from AI response if present.

    Returns (clean_text, action_dict_or_None).
    """
    pattern = r'```json\s*(\{[^}]+\})\s*```'
    match = re.search(pattern, ai_text)
    if match:
        try:
            action = json.loads(match.group(1))
            clean = ai_text[:match.start()].strip()
            return clean, action
        except json.JSONDecodeError:
            pass

    # Try inline JSON
    pattern2 = r'\{"action"\s*:\s*"[^"]+?"[^}]*\}'
    match2 = re.search(pattern2, ai_text)
    if match2:
        try:
            action = json.loads(match2.group(0))
            clean = ai_text[:match2.start()].strip()
            return clean, action
        except json.JSONDecodeError:
            pass

    return ai_text, None


async def _gather_plane_data(user_message: str, user_email: str) -> str:
    """Intelligently gather Plane data based on the user's question."""
    msg_lower = user_message.lower()
    data_parts = []

    # Check for sequence ID reference
    seq_match = re.search(r'#(\d+)', user_message)
    if seq_match:
        seq_id = int(seq_match.group(1))
        result = await plane_service.find_issue_by_seq(seq_id)
        if result:
            _, _, issue = result
            data_parts.append(f"Задача #{seq_id}: {json.dumps(issue, ensure_ascii=False)}")
            try:
                comments = await plane_api.get_issue_comments(result[0], issue['id'])
                if comments:
                    comment_lines = [f"  - {c.get('comment_stripped', c.get('comment_html', ''))[:100]}" for c in comments[:5]]
                    data_parts.append(f"Комментарии к #{seq_id}:\n" + "\n".join(comment_lines))
            except Exception:
                pass

    # Keywords for different data
    keywords_my_tasks = ['мои', 'мне', 'заняться', 'задач', 'дела', 'todo', 'сделать', 'срочн']
    keywords_overdue = ['просроч', 'проебал', 'забыл', 'пропустил', 'overdue', 'stale', 'завис', 'горит']
    keywords_project = ['проект', 'project']
    keywords_workload = ['нагрузк', 'workload', 'команд', 'кто чем']
    keywords_status = ['статус', 'status', 'обзор', 'сводк', 'итог']

    if any(kw in msg_lower for kw in keywords_my_tasks) or not data_parts:
        data_parts.append(await plane_service.get_my_tasks_summary(user_email))

    if any(kw in msg_lower for kw in keywords_overdue):
        data_parts.append(await plane_service.get_overdue_summary(user_email))

    if any(kw in msg_lower for kw in keywords_workload):
        data_parts.append(await plane_service.get_workload_summary())

    # Check for specific project mentions
    if any(kw in msg_lower for kw in keywords_project):
        words = user_message.upper().split()
        for word in words:
            if len(word) >= 2 and word not in ('ПО', 'НА', 'ЧТО', 'КАК', 'ПРОЕКТ', 'PROJECT', 'ПРОЕКТУ'):
                result = await plane_service.get_project_tasks_summary(word)
                if 'не найден' not in result:
                    data_parts.append(result)
                    break

    if any(kw in msg_lower for kw in keywords_status):
        data_parts.append(await plane_service.get_projects_list())
        if not any(kw in msg_lower for kw in keywords_my_tasks):
            data_parts.append(await plane_service.get_my_tasks_summary(user_email))

    if not data_parts:
        data_parts.append(await plane_service.get_my_tasks_summary(user_email))

    return "\n\n".join(data_parts)


async def _process_message(user_message: str, user_id: int, state: FSMContext) -> str:
    """Process a user message through AI and return HTML response."""
    user_email = _get_plane_email(user_id)

    # Gather data from Plane
    plane_data = await _gather_plane_data(user_message, user_email)

    # Get conversation history
    conv_history = await context_manager.get_last_context_summary(user_id)

    # Get workspace context (members, projects)
    members = await plane_service.get_members_list()
    workspace_ctx = f"Участники: {members}" if members else ""

    # Build system prompt
    system = SYSTEM_PROMPT.format(
        workspace_context=workspace_ctx,
        conversation_history=conv_history or "(новый разговор)",
        plane_data=plane_data[:6000],
    )

    # Call AI
    try:
        response = await ai_manager.chat(
            user_message=user_message,
            system_prompt=system,
        )
        ai_text = response.content if hasattr(response, 'content') else str(response)
    except Exception as e:
        bot_logger.error(f"AI error in /plane: {e}")
        safe = _escape_html(plane_data[:3000])
        return f"<i>AI недоступен, вот сырые данные:</i>\n\n<code>{safe}</code>"

    # Save to conversation context
    await context_manager.add_message(user_id, "user", user_message)
    await context_manager.add_message(user_id, "assistant", ai_text[:500])

    # Extract action if AI wants to perform a write
    text, action = _extract_action(ai_text)

    if action:
        # Ensure there's always visible text before confirmation buttons
        if not text:
            seq = action.get("seq_id", "?")
            action_name = action.get("action", "")
            fallback_labels = {
                "close_issue": f"Закрываю задачу <b>#{seq}</b>",
                "assign_issue": f"Назначаю <b>#{seq}</b> на {action.get('assignee', '?')}",
                "comment_issue": f"Добавляю комментарий к <b>#{seq}</b>",
            }
            text = fallback_labels.get(action_name, f"Выполняю действие с #{seq}")

        await state.update_data(pending_action=action)
        await state.set_state(PlaneAssistantStates.confirm_write)
        return text, action  # Tuple signals caller to show confirmation

    return text


@router.message(Command("plane"))
async def cmd_plane(message: Message, state: FSMContext, bot: Bot):
    """Entry point: /plane [question]."""
    if not settings.is_admin(message.from_user.id):
        await message.answer("Admin only", parse_mode=None)
        return

    if not plane_api.configured:
        await message.answer("Plane API не настроен", parse_mode=None)
        return

    if ai_manager.providers_count == 0:
        await message.answer("AI провайдер не настроен", parse_mode=None)
        return

    # Extract text after /plane
    args = message.text.split(maxsplit=1)
    user_text = args[1].strip() if len(args) > 1 else None

    if not user_text:
        # Show help + enter conversation mode
        await state.set_state(PlaneAssistantStates.conversation)
        help_text = (
            "<b>Plane AI Assistant</b>\n\n"
            "Напиши что угодно о задачах:\n"
            "- <i>чем мне заняться?</i>\n"
            "- <i>какие срочные задачи?</i>\n"
            "- <i>где я проебался?</i>\n"
            "- <i>что по HARZL?</i>\n"
            "- <i>закрой #123</i>\n"
            "- <i>назначь #456 на Тимофея</i>\n"
            "- <i>напиши коммент к #789: готово</i>\n\n"
            "Или отправь голосовое.\n"
            "Для выхода: /plane_exit"
        )
        await message.answer(help_text, parse_mode="HTML")
        return

    # Process the query
    await state.set_state(PlaneAssistantStates.conversation)
    status = await message.answer("Думаю...", parse_mode=None)

    try:
        result = await _process_message(user_text, message.from_user.id, state)

        if isinstance(result, tuple):
            text, action = result
            await _send_confirmation(status, text, action)
        else:
            await _safe_edit(status, result)
    except Exception as e:
        bot_logger.error(f"/plane error: {e}", exc_info=True)
        await status.edit_text(f"Ошибка: {e}", parse_mode=None)


@router.message(PlaneAssistantStates.conversation, F.text, ~F.text.startswith("/"))
async def handle_followup(message: Message, state: FSMContext, bot: Bot):
    """Handle follow-up messages in conversation mode."""
    status = await message.answer("Думаю...", parse_mode=None)

    try:
        result = await _process_message(message.text, message.from_user.id, state)

        if isinstance(result, tuple):
            text, action = result
            await _send_confirmation(status, text, action)
        else:
            await _safe_edit(status, result)
    except Exception as e:
        bot_logger.error(f"/plane followup error: {e}", exc_info=True)
        await status.edit_text(f"Ошибка: {e}", parse_mode=None)


@router.message(PlaneAssistantStates.conversation, F.voice)
async def handle_voice(message: Message, state: FSMContext, bot: Bot):
    """Handle voice messages — transcribe with Whisper, then process."""
    status = await message.answer("Транскрибирую голосовое...", parse_mode=None)

    try:
        # Download voice file
        file = await bot.get_file(message.voice.file_id)
        tmp_path = os.path.join(tempfile.gettempdir(), f"plane_voice_{message.from_user.id}.ogg")
        await bot.download_file(file.file_path, tmp_path)

        # Transcribe
        from ...handlers.voice_transcription import transcribe_with_whisper
        transcription = await transcribe_with_whisper(tmp_path)

        if not transcription:
            await status.edit_text("Не удалось распознать голосовое", parse_mode=None)
            return

        await status.edit_text(f"Распознано: <i>{_escape_html(transcription[:200])}</i>\n\nДумаю...", parse_mode="HTML")

        # Process transcription as text
        result = await _process_message(transcription, message.from_user.id, state)

        if isinstance(result, tuple):
            text, action = result
            full_text = f"<i>Голос:</i> {_escape_html(transcription[:150])}\n\n{text}"
            await _send_confirmation(status, full_text, action)
        else:
            prefix = f"<i>Голос:</i> {_escape_html(transcription[:150])}\n\n"
            await _safe_edit(status, prefix + result)

    except Exception as e:
        bot_logger.error(f"/plane voice error: {e}", exc_info=True)
        await status.edit_text(f"Ошибка: {e}", parse_mode=None)
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


@router.message(Command("plane_exit"))
async def cmd_plane_exit(message: Message, state: FSMContext):
    """Exit conversation mode."""
    await state.clear()
    await context_manager.clear_context(message.from_user.id)
    await message.answer("Plane assistant завершён.", parse_mode=None)


# ---- Write action confirmation ----

async def _send_confirmation(status_msg: Message, text: str, action: dict):
    """Show confirmation keyboard for write action."""
    action_name = action.get("action", "?")
    seq = action.get("seq_id", "?")

    action_labels = {
        "close_issue": f"Закрыть #{seq}",
        "assign_issue": f"Назначить #{seq} на {action.get('assignee', '?')}",
        "comment_issue": f"Коммент к #{seq}",
    }
    label = action_labels.get(action_name, action_name)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"Подтвердить: {label}", callback_data="plane_act:confirm"),
            InlineKeyboardButton(text="Отмена", callback_data="plane_act:cancel"),
        ]
    ])

    await _safe_edit(status_msg, text, reply_markup=keyboard)


@router.callback_query(F.data == "plane_act:confirm")
async def on_confirm(callback: CallbackQuery, state: FSMContext):
    """Execute confirmed write action."""
    data = await state.get_data()
    action = data.get("pending_action")

    if not action:
        await callback.answer("Действие не найдено", show_alert=True)
        return

    await callback.answer("Выполняю...")
    action_name = action.get("action", "")
    seq_id = action.get("seq_id")

    result_text = "Неизвестное действие"

    if seq_id:
        found = await plane_service.find_issue_by_seq(seq_id)
        if not found:
            result_text = f"Задача #{seq_id} не найдена"
        else:
            project_id, pident, issue = found

            if action_name == "close_issue":
                ok = await plane_service.close_issue(project_id, issue["id"])
                result_text = f"Задача #{seq_id} закрыта" if ok else f"Не удалось закрыть #{seq_id}"
                if ok and action.get("comment"):
                    await plane_service.add_comment(project_id, issue["id"], action["comment"])

            elif action_name == "assign_issue":
                assignee = action.get("assignee", "")
                name = await plane_service.assign_issue(project_id, issue["id"], assignee)
                result_text = f"#{seq_id} назначена на {name}" if name else f"Не нашёл '{assignee}' в команде"

            elif action_name == "comment_issue":
                comment = action.get("comment", "")
                ok = await plane_service.add_comment(project_id, issue["id"], comment)
                result_text = f"Комментарий к #{seq_id} добавлен" if ok else f"Ошибка при добавлении комментария"

    await callback.message.edit_text(f"<b>{result_text}</b>", parse_mode="HTML")
    await state.set_state(PlaneAssistantStates.conversation)
    await state.update_data(pending_action=None)


@router.callback_query(F.data == "plane_act:cancel")
async def on_cancel(callback: CallbackQuery, state: FSMContext):
    """Cancel write action."""
    await state.update_data(pending_action=None)
    await state.set_state(PlaneAssistantStates.conversation)
    await callback.message.edit_text("Действие отменено.", parse_mode=None)
    await callback.answer()


# ---- Helpers ----

async def _safe_edit(msg: Message, text: str, **kwargs):
    """Edit message with HTML, fallback to plain text on parse error."""
    if not text:
        text = "(пустой ответ)"

    # Truncate for Telegram limit
    if len(text) > 4000:
        text = text[:3950] + "\n\n<i>...обрезано</i>"

    try:
        await msg.edit_text(text, parse_mode="HTML", **kwargs)
    except Exception:
        # Fallback — strip HTML tags
        clean = re.sub(r'<[^>]+>', '', text)
        try:
            await msg.edit_text(clean[:4000], parse_mode=None, **kwargs)
        except Exception as e:
            bot_logger.error(f"Failed to edit message: {e}")
