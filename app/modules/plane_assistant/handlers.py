"""
/plane AI assistant — natural language interface to Plane.so.

AI-first: all user messages are processed by LLM which decides
what data to fetch and how to respond. Optimized for ADHD users.

Multi-model: Groq (fast, smart) → OpenRouter (free fallback).
"""

import asyncio
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

DEFAULT_EMAIL = "zarudesu@gmail.com"

AI_TIMEOUT = 30  # seconds
AI_PROVIDERS = ["groq", "openrouter"]


def _get_plane_email(user_id: int) -> str:
    """Get Plane email from daily_tasks_service settings (DB) or fallback."""
    try:
        from ...services.daily_tasks_service import daily_tasks_service
        if daily_tasks_service:
            admin_settings = daily_tasks_service.get_admin_settings(user_id)
            if admin_settings:
                email = admin_settings.get('plane_email') if isinstance(admin_settings, dict) else getattr(admin_settings, 'plane_email', None)
                if email:
                    return email
    except Exception:
        pass
    return DEFAULT_EMAIL


SYSTEM_PROMPT = """Ты — AI-ассистент для задач в Plane.so. Помоги IT-специалисту с СДВГ.

ПРАВИЛА:
1. КРАТКО — максимум 5-7 строк. Длинные тексты парализуют.
2. Выделяй ГЛАВНОЕ: "у тебя X срочных, Y просроченных, начни с Z".
3. Будь человечным, не формальным.
4. ОБЯЗАТЕЛЬНО используй <b>жирный</b> для важного, <i>курсив</i> для пояснений.
5. Для действий — СНАЧАЛА текст, ПОТОМ один JSON-блок. ДОСТУПНЫЕ ДЕЙСТВИЯ:
   {{"action": "close_issue", "seq_id": 123, "comment": "optional"}}
   {{"action": "assign_issue", "seq_id": 123, "assignee": "Тимофей"}}
   {{"action": "unassign_issue", "seq_id": 123}}
   {{"action": "comment_issue", "seq_id": 123, "comment": "текст"}}
   {{"action": "update_status", "seq_id": 123, "status": "started"}}
   {{"action": "update_priority", "seq_id": 123, "priority": "high"}}
   {{"action": "set_deadline", "seq_id": 123, "target_date": "2026-02-15"}}
   {{"action": "set_start_date", "seq_id": 123, "start_date": "2026-02-10"}}
   {{"action": "rename_issue", "seq_id": 123, "new_name": "Новое название"}}
   {{"action": "set_description", "seq_id": 123, "description": "Подробное описание задачи"}}
   {{"action": "archive_issue", "seq_id": 123}}
   {{"action": "create_task", "project": "HARZL", "name": "Название задачи", "priority": "high", "assignee": "Тимофей"}}
6. СТАТУСЫ (status): "backlog", "unstarted", "started", "completed", "cancelled".
   "в работе" = "started", "бэклог" = "backlog", "сделано" = "completed".
   "закрой" / "выполнено" / "done" → используй close_issue, НЕ update_status!
7. ПРИОРИТЕТЫ (priority): "urgent", "high", "medium", "low", "none".
   Даты: "дедлайн/начало завтра" → вычисли дату YYYY-MM-DD. "" = убрать.
8. НИКОГДА не возвращай JSON с "is_task", "confidence", "task_description" — это чужой формат. Используй ТОЛЬКО действия выше или обычный текст.
9. Работай ТОЛЬКО с реальными данными ниже.
10. "Чем заняться" → TOP-3 задачи + ПОЧЕМУ именно они.
11. Задачи старше 3 месяцев без обновлений — предложи закрыть или переназначить.
12. Если пользователь указывает задачу ПО ИМЕНИ (без #номера), найди её в данных и используй seq_id.
    ВСЕГДА указывай seq_id в JSON — это ОБЯЗАТЕЛЬНОЕ поле.

КОНТЕКСТ WORKSPACE:
{workspace_context}

ПРЕДЫДУЩИЙ РАЗГОВОР:
{conversation_history}

ДАННЫЕ ИЗ PLANE:
{plane_data}
"""

# ---- Fuzzy project matching ----

PROJECT_ALIASES = {
    "харц": "HARZL", "harz": "HARZL", "харзл": "HARZL",
    "хг": "HG", "сад": "HG", "здоров": "HG", "healthgarden": "HG",
    "дельт": "DELTA", "delta": "DELTA",
    "вонд": "VONDI", "парк": "VONDI",
    "ива": "IVA", "iva": "IVA",
    "веха": "VEHA",
    "медвед": "SMED", "северн": "SMED",
    "hhvip": "HHVIP", "hhivp": "HHVIP", "внутр": "HHVIP",
    "бот": "HHVIP",
}


def _fuzzy_match_project(text: str) -> str | None:
    """Try to match a project from free-form text."""
    text_lower = text.lower()
    for alias, ident in PROJECT_ALIASES.items():
        if alias in text_lower:
            return ident
    # Try direct identifier match (uppercase words)
    for word in text.upper().split():
        if len(word) >= 2 and word not in ('ПО', 'НА', 'ЧТО', 'КАК', 'ПРОЕКТ', 'PROJECT', 'ПРОЕКТУ', 'ЗАДАЧИ'):
            return word
    return None


# ---- Helpers ----

def _escape_html(text: str) -> str:
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _extract_action(ai_text: str) -> tuple:
    """Extract JSON action block from AI response.
    Returns (clean_text, action_dict_or_None).
    """
    # Try ```json block (multiline, greedy inner braces)
    match = re.search(r'```json\s*(\{.*?\})\s*```', ai_text, re.DOTALL)
    if match:
        try:
            action = json.loads(match.group(1))
            if "action" in action:
                clean = (ai_text[:match.start()] + ai_text[match.end():]).strip()
                return clean, action
        except json.JSONDecodeError:
            pass

    # Try ``` block without json label
    match1b = re.search(r'```\s*(\{"action".*?\})\s*```', ai_text, re.DOTALL)
    if match1b:
        try:
            action = json.loads(match1b.group(1))
            clean = (ai_text[:match1b.start()] + ai_text[match1b.end():]).strip()
            return clean, action
        except json.JSONDecodeError:
            pass

    # Try inline JSON with "action" key (balanced braces)
    for m in re.finditer(r'\{[^{}]*"action"\s*:[^{}]*\}', ai_text):
        try:
            action = json.loads(m.group(0))
            clean = (ai_text[:m.start()] + ai_text[m.end():]).strip()
            return clean, action
        except json.JSONDecodeError:
            continue

    # Final cleanup: remove any leftover JSON-like blocks that AI might have emitted
    cleaned = re.sub(r'```json\s*\{.*?\}\s*```', '', ai_text, flags=re.DOTALL).strip()
    cleaned = re.sub(r'```\s*\{.*?\}\s*```', '', cleaned, flags=re.DOTALL).strip()

    # If the entire response is a JSON object without "action" key — wrong format
    if cleaned.startswith('{') and cleaned.endswith('}') and '"action"' not in cleaned:
        try:
            obj = json.loads(cleaned)
            desc = obj.get("task_description") or obj.get("description") or ""
            if desc:
                cleaned = desc
            else:
                cleaned = ""
        except json.JSONDecodeError:
            pass

    # Strip remaining stray is_task JSON fragments from mixed text
    cleaned = re.sub(r'\{[^{}]*"is_task"\s*:[^{}]*\}', '', cleaned).strip()

    if not cleaned:
        cleaned = "Не удалось обработать запрос. Попробуйте переформулировать."

    return cleaned, None


def _classify_query(msg: str) -> str:
    """Classify query complexity: 'action' (simple) or 'analysis' (needs smart model)."""
    msg_lower = msg.lower()
    action_kw = [
        'закрой', 'назначь', 'коммент', 'создай', 'удали', 'close', 'assign',
        'смени', 'статус', 'приоритет', 'в работе', 'в работу', 'бэклог',
        'дедлайн', 'срок', 'deadline', 'переименуй', 'rename',
        'сними', 'убери исполн', 'unassign',
        'архив', 'archive', 'описание', 'description', 'начало', 'start_date',
    ]
    if any(kw in msg_lower for kw in action_kw):
        return "action"
    return "analysis"


def _get_provider_order(query_type: str) -> list:
    """Get provider priority based on query complexity.

    Analysis queries → Groq (70B, smart) first, then Gemini, then OpenRouter.
    Simple actions → OpenRouter (fast, free) first, Gemini, then Groq.
    """
    if query_type == "action":
        return ["openrouter", "gemini", "groq"]
    return ["groq", "gemini", "openrouter"]


async def _ai_chat(user_message: str, system_prompt: str) -> str:
    """Call AI with timeout and multi-provider fallback."""
    query_type = _classify_query(user_message)
    providers = _get_provider_order(query_type)
    last_error = None

    for provider_name in providers:
        provider = ai_manager.get_provider(provider_name)
        if not provider:
            continue

        try:
            response = await asyncio.wait_for(
                ai_manager.chat(
                    user_message=user_message,
                    system_prompt=system_prompt,
                    provider_name=provider_name,
                ),
                timeout=AI_TIMEOUT,
            )
            content = response.content if hasattr(response, 'content') else str(response)
            bot_logger.info(f"/plane AI [{query_type}] via {provider_name} ({len(content)} chars)")
            return content
        except asyncio.TimeoutError:
            bot_logger.warning(f"/plane AI timeout on {provider_name} ({AI_TIMEOUT}s)")
            last_error = f"Timeout ({provider_name})"
        except Exception as e:
            bot_logger.warning(f"/plane AI error on {provider_name}: {e}")
            last_error = str(e)

    raise RuntimeError(last_error or "No AI providers available")


# ---- Data gathering ----

async def _gather_plane_data(user_message: str, user_email: str) -> str:
    """Gather Plane data based on the user's question."""
    msg_lower = user_message.lower()
    data_parts = []

    # Sequence ID reference (#123)
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
                    lines = [f"  - {c.get('comment_stripped', c.get('comment_html', ''))[:100]}" for c in comments[:5]]
                    data_parts.append(f"Комментарии к #{seq_id}:\n" + "\n".join(lines))
            except Exception:
                pass

    # Keyword categories
    kw_tasks = ['мои', 'мне', 'заняться', 'задач', 'дела', 'todo', 'сделать', 'срочн', 'приоритет']
    kw_overdue = ['просроч', 'проебал', 'забыл', 'пропустил', 'overdue', 'stale', 'завис', 'горит']
    kw_project = ['проект', 'project', 'что по']
    kw_workload = ['нагрузк', 'workload', 'команд', 'кто чем', 'кто занят']
    kw_status = ['обзор', 'сводк', 'итог']
    kw_mutation = ['смени', 'поменяй', 'измени', 'переведи', 'статус', 'в работе', 'в работу']

    if any(kw in msg_lower for kw in kw_tasks) or not data_parts:
        data_parts.append(await plane_service.get_my_tasks_summary(user_email))

    if any(kw in msg_lower for kw in kw_overdue):
        data_parts.append(await plane_service.get_overdue_summary(user_email))

    if any(kw in msg_lower for kw in kw_workload):
        data_parts.append(await plane_service.get_workload_summary())

    # Fuzzy project matching
    if any(kw in msg_lower for kw in kw_project) or any(alias in msg_lower for alias in PROJECT_ALIASES):
        project_id = _fuzzy_match_project(user_message)
        if project_id:
            result = await plane_service.get_project_tasks_summary(project_id)
            if 'не найден' not in result:
                data_parts.append(result)

    # Status mutation request — load project tasks for the mentioned project
    if any(kw in msg_lower for kw in kw_mutation):
        project_id = _fuzzy_match_project(user_message)
        if project_id:
            result = await plane_service.get_project_tasks_summary(project_id)
            if 'не найден' not in result:
                data_parts.append(result)

    if any(kw in msg_lower for kw in kw_status):
        data_parts.append(await plane_service.get_projects_list())
        if not any(kw in msg_lower for kw in kw_tasks):
            data_parts.append(await plane_service.get_my_tasks_summary(user_email))

    if not data_parts:
        data_parts.append(await plane_service.get_my_tasks_summary(user_email))

    return "\n\n".join(data_parts)


# ---- Core processing ----

async def _process_message(user_message: str, user_id: int, state: FSMContext, status_msg: Message = None):
    """Process a user message through AI and return HTML response."""
    user_email = _get_plane_email(user_id)

    if status_msg:
        try:
            await status_msg.edit_text("Загружаю данные из Plane...", parse_mode=None)
        except Exception:
            pass

    plane_data = await _gather_plane_data(user_message, user_email)

    if status_msg:
        try:
            await status_msg.edit_text("Анализирую...", parse_mode=None)
        except Exception:
            pass

    conv_history = await context_manager.get_last_context_summary(user_id)

    members = await plane_service.get_members_list()
    workspace_ctx = f"Участники: {members}" if members else ""

    system = SYSTEM_PROMPT.format(
        workspace_context=workspace_ctx,
        conversation_history=conv_history or "(новый разговор)",
        plane_data=plane_data[:6000],
    )

    try:
        ai_text = await _ai_chat(user_message, system)
    except Exception as e:
        bot_logger.error(f"AI error in /plane: {e}")
        safe = _escape_html(plane_data[:3000])
        return f"<i>AI недоступен, вот сырые данные:</i>\n\n<pre>{safe}</pre>"

    # Save to conversation
    await context_manager.add_message(user_id, "user", user_message)
    await context_manager.add_message(user_id, "assistant", ai_text[:500])

    # Extract action
    text, action = _extract_action(ai_text)

    if action:
        # create_task → interactive draft flow
        if action.get("action") == "create_task":
            draft = {
                "project": action.get("project", ""),
                "name": action.get("name", ""),
                "priority": action.get("priority", "none"),
                "assignee": action.get("assignee", ""),
                "target_date": action.get("target_date", ""),
                "description": action.get("description", ""),
            }
            await state.update_data(task_draft=draft)
            await state.set_state(PlaneAssistantStates.drafting_task)
            return "DRAFT_TASK", draft

        if not text:
            seq = action.get("seq_id", "?")
            act = action.get("action", "")
            fallbacks = {
                "close_issue": f"Закрываю задачу <b>#{seq}</b>",
                "assign_issue": f"Назначаю <b>#{seq}</b> на {action.get('assignee', '?')}",
                "unassign_issue": f"Снимаю исполнителя с <b>#{seq}</b>",
                "comment_issue": f"Добавляю комментарий к <b>#{seq}</b>",
                "update_status": f"Меняю статус <b>#{seq}</b> → {action.get('status', '?')}",
                "update_priority": f"Меняю приоритет <b>#{seq}</b> → {action.get('priority', '?')}",
                "set_deadline": f"Дедлайн <b>#{seq}</b> → {action.get('target_date', '?')}",
                "set_start_date": f"Начало <b>#{seq}</b> → {action.get('start_date', '?')}",
                "rename_issue": f"Переименовываю <b>#{seq}</b>",
                "set_description": f"Описание <b>#{seq}</b>",
                "archive_issue": f"Архивирую <b>#{seq}</b>",
            }
            text = fallbacks.get(act, f"Выполняю действие с #{seq}")

        await state.update_data(pending_action=action)
        await state.set_state(PlaneAssistantStates.confirm_write)
        return text, action

    return text


# ---- Handlers ----

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

    args = message.text.split(maxsplit=1)
    user_text = args[1].strip() if len(args) > 1 else None

    if not user_text:
        await state.set_state(PlaneAssistantStates.conversation)
        help_text = (
            "<b>Plane AI Assistant</b>\n\n"
            "Напиши что угодно о задачах:\n"
            "- <i>чем мне заняться?</i>\n"
            "- <i>какие срочные задачи?</i>\n"
            "- <i>где я проебался?</i>\n"
            "- <i>что по харцу?</i>\n"
            "- <i>закрой #123</i>\n"
            "- <i>создай задачу в HARZL: настроить VPN</i>\n"
            "- <i>назначь #456 на Тимофея</i>\n\n"
            "Голосовые тоже работают.\n"
            "Выход: /plane_exit"
        )
        await message.answer(help_text, parse_mode="HTML")
        return

    await state.set_state(PlaneAssistantStates.conversation)
    status = await message.answer("Думаю...", parse_mode=None)

    try:
        result = await _process_message(user_text, message.from_user.id, state, status_msg=status)
        await _dispatch_result(result, status, state)
    except Exception as e:
        bot_logger.error(f"/plane error: {e}", exc_info=True)
        await status.edit_text(f"Ошибка: {e}", parse_mode=None)


@router.message(PlaneAssistantStates.conversation, F.text, ~F.text.startswith("/"))
async def handle_followup(message: Message, state: FSMContext, bot: Bot):
    """Handle follow-up messages in conversation mode."""
    status = await message.answer("Думаю...", parse_mode=None)

    try:
        result = await _process_message(message.text, message.from_user.id, state, status_msg=status)
        await _dispatch_result(result, status, state)
    except Exception as e:
        bot_logger.error(f"/plane followup error: {e}", exc_info=True)
        await status.edit_text(f"Ошибка: {e}", parse_mode=None)


@router.message(PlaneAssistantStates.conversation, F.voice)
async def handle_voice(message: Message, state: FSMContext, bot: Bot):
    """Handle voice messages — transcribe with Whisper, then process."""
    status = await message.answer("Транскрибирую голосовое...", parse_mode=None)
    tmp_path = None

    try:
        file = await bot.get_file(message.voice.file_id)
        tmp_path = os.path.join(tempfile.gettempdir(), f"plane_voice_{message.from_user.id}.ogg")
        await bot.download_file(file.file_path, tmp_path)

        from ...handlers.voice_transcription import transcribe_with_whisper
        transcription = await transcribe_with_whisper(tmp_path)

        if not transcription:
            await status.edit_text("Не удалось распознать голосовое", parse_mode=None)
            return

        await status.edit_text(
            f"Распознано: <i>{_escape_html(transcription[:200])}</i>\n\nДумаю...",
            parse_mode="HTML",
        )

        result = await _process_message(transcription, message.from_user.id, state)

        voice_prefix = f"<i>Голос:</i> {_escape_html(transcription[:150])}\n\n"
        await _dispatch_result(result, status, state, text_prefix=voice_prefix)

    except Exception as e:
        bot_logger.error(f"/plane voice error: {e}", exc_info=True)
        await status.edit_text(f"Ошибка: {e}", parse_mode=None)
    finally:
        if tmp_path:
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

async def _dispatch_result(result, status_msg: Message, state: FSMContext, text_prefix: str = ""):
    """Route _process_message result to the right UI."""
    if isinstance(result, tuple):
        marker, payload = result
        if marker == "DRAFT_TASK":
            # Interactive task draft
            text = _render_draft(payload)
            kb = _draft_keyboard(payload)
            if text_prefix:
                text = text_prefix + text
            await _safe_edit(status_msg, text, reply_markup=kb)
            return
        # Regular confirm (close/assign/comment)
        text, action = marker, payload
        if text_prefix:
            text = text_prefix + text
        await _send_confirmation(status_msg, text, action)
    else:
        if text_prefix:
            result = text_prefix + result
        await _safe_edit(status_msg, result)


PRIORITY_LABELS = {
    "urgent": "🔴 Срочно",
    "high": "🟠 Высокий",
    "medium": "🟡 Средний",
    "low": "🟢 Низкий",
    "none": "⚪ Без приоритета",
}


def _render_draft(draft: dict) -> str:
    """Render task draft as HTML message."""
    project = _escape_html(draft.get("project", "—"))
    name = _escape_html(draft.get("name", "—"))
    prio = PRIORITY_LABELS.get(draft.get("priority", "none"), "⚪ Без приоритета")
    assignee = _escape_html(draft.get("assignee", "")) or "не указан"
    target = _escape_html(draft.get("target_date", "")) or "не указан"
    desc = _escape_html(draft.get("description", "")) or "—"

    lines = [
        "<b>📋 Новая задача (черновик)</b>",
        "",
        f"📌 <b>Проект:</b> {project}",
        f"📝 <b>Название:</b> {name}",
        f"🔥 <b>Приоритет:</b> {prio}",
        f"👤 <b>Исполнитель:</b> {assignee}",
        f"📅 <b>Дедлайн:</b> {target}",
    ]
    if desc != "—":
        lines.append(f"📄 <b>Описание:</b> {desc}")

    lines.append("")
    lines.append("<i>Напиши чтобы изменить, или нажми кнопку:</i>")
    return "\n".join(lines)


def _draft_keyboard(draft: dict) -> InlineKeyboardMarkup:
    """Build inline keyboard for task draft."""
    current = draft.get("priority", "none")

    prio_buttons = []
    for key, label in PRIORITY_LABELS.items():
        text = f"• {label} •" if key == current else label
        prio_buttons.append(
            InlineKeyboardButton(text=text, callback_data=f"draft_prio:{key}")
        )

    rows = [
        prio_buttons[:3],
        prio_buttons[3:],
        [
            InlineKeyboardButton(text="✅ Создать", callback_data="draft:create"),
            InlineKeyboardButton(text="🗑 Очистить", callback_data="draft:clear"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data.startswith("draft_prio:"))
async def on_draft_priority(callback: CallbackQuery, state: FSMContext):
    """Change priority in task draft."""
    prio = callback.data.split(":", 1)[1]
    data = await state.get_data()
    draft = data.get("task_draft", {})
    draft["priority"] = prio
    await state.update_data(task_draft=draft)
    await callback.answer(PRIORITY_LABELS.get(prio, prio))

    text = _render_draft(draft)
    kb = _draft_keyboard(draft)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        pass


@router.callback_query(F.data == "draft:create")
async def on_draft_create(callback: CallbackQuery, state: FSMContext):
    """Create task from draft."""
    data = await state.get_data()
    draft = data.get("task_draft", {})

    if not draft.get("name") or not draft.get("project"):
        await callback.answer("Укажи проект и название", show_alert=True)
        return

    await callback.answer("Создаю задачу...")

    result_text = await _handle_create_task_from_draft(draft)
    await callback.message.edit_text(f"<b>{result_text}</b>", parse_mode="HTML")
    await state.update_data(task_draft=None)
    await state.set_state(PlaneAssistantStates.conversation)


@router.callback_query(F.data == "draft:clear")
async def on_draft_clear(callback: CallbackQuery, state: FSMContext):
    """Clear task draft, back to conversation."""
    await state.update_data(task_draft=None)
    await state.set_state(PlaneAssistantStates.conversation)
    await callback.message.edit_text("Черновик очищен.", parse_mode=None)
    await callback.answer()


@router.message(PlaneAssistantStates.drafting_task, F.text, ~F.text.startswith("/"))
async def handle_draft_edit(message: Message, state: FSMContext):
    """Handle natural-language edits to task draft."""
    data = await state.get_data()
    draft = data.get("task_draft", {})
    text = message.text.strip()
    text_lower = text.lower()

    changed = False

    # Priority keywords
    prio_map = {
        "срочн": "urgent", "urgent": "urgent", "критич": "urgent",
        "высок": "high", "high": "high", "важн": "high",
        "средн": "medium", "medium": "medium", "норм": "medium",
        "низк": "low", "low": "low",
    }
    for kw, val in prio_map.items():
        if kw in text_lower:
            draft["priority"] = val
            changed = True
            break

    # Assignee: "на Тимофея", "назначь Тимофею", "исполнитель Тимофей"
    assign_match = re.search(r'(?:на|назначь|исполнитель)\s+([А-Яа-яA-Za-z]+)', text)
    if assign_match:
        draft["assignee"] = assign_match.group(1)
        changed = True

    # Date: "дедлайн завтра", "до 15.02", "срок 2026-02-15"
    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', text)
    if date_match:
        draft["target_date"] = date_match.group(1)
        changed = True
    elif re.search(r'(\d{1,2})[./](\d{1,2})', text):
        dm = re.search(r'(\d{1,2})[./](\d{1,2})', text)
        from datetime import date as dt_date
        try:
            day, month = int(dm.group(1)), int(dm.group(2))
            year = dt_date.today().year
            d = dt_date(year, month, day)
            if d < dt_date.today():
                d = d.replace(year=year + 1)
            draft["target_date"] = d.isoformat()
            changed = True
        except ValueError:
            pass
    elif "завтра" in text_lower:
        from datetime import date as dt_date, timedelta
        draft["target_date"] = (dt_date.today() + timedelta(days=1)).isoformat()
        changed = True
    elif "послезавтра" in text_lower:
        from datetime import date as dt_date, timedelta
        draft["target_date"] = (dt_date.today() + timedelta(days=2)).isoformat()
        changed = True
    elif re.search(r'через\s+(\d+)\s+дн', text_lower):
        from datetime import date as dt_date, timedelta
        days = int(re.search(r'через\s+(\d+)\s+дн', text_lower).group(1))
        draft["target_date"] = (dt_date.today() + timedelta(days=days)).isoformat()
        changed = True
    elif "неделю" in text_lower or "неделя" in text_lower:
        from datetime import date as dt_date, timedelta
        draft["target_date"] = (dt_date.today() + timedelta(days=7)).isoformat()
        changed = True

    # Description: "описание: ..." or anything else that didn't match above
    desc_match = re.search(r'описание[:\s]+(.+)', text, re.IGNORECASE)
    if desc_match:
        draft["description"] = desc_match.group(1).strip()
        changed = True

    # Name change: "название: ..."
    name_match = re.search(r'(?:название|задача)[:\s]+(.+)', text, re.IGNORECASE)
    if name_match:
        draft["name"] = name_match.group(1).strip()
        changed = True

    # Project change: "проект: ..."
    proj_match = re.search(r'проект[:\s]+(\S+)', text, re.IGNORECASE)
    if proj_match:
        draft["project"] = proj_match.group(1).strip()
        changed = True

    if not changed:
        # Treat whole text as description if nothing matched
        draft["description"] = text
        changed = True

    await state.update_data(task_draft=draft)
    reply = _render_draft(draft)
    kb = _draft_keyboard(draft)
    await message.answer(reply, parse_mode="HTML", reply_markup=kb)


async def _handle_create_task_from_draft(draft: dict) -> str:
    """Create a Plane task from the interactive draft."""
    project_ident = draft.get("project", "")
    name = draft.get("name", "")
    priority = draft.get("priority", "none")
    assignee_name = draft.get("assignee")
    target_date = draft.get("target_date") or None
    description = draft.get("description", "")

    if not project_ident or not name:
        return "✗ Не указан проект или название задачи"

    try:
        # Find project
        projects = await plane_api.get_all_projects()
        if not projects:
            return "✗ Не удалось загрузить проекты из Plane"

        project = _find_project(projects, project_ident)
        if not project:
            avail = ", ".join(p.get('identifier', '?') for p in projects[:10])
            return f"✗ Проект '{project_ident}' не найден. Есть: {avail}"

        pid = project['id']
        pname = project.get('identifier', '?')

        # Resolve assignee
        assignee_ids = _resolve_assignee_ids(assignee_name, await plane_api.get_workspace_members()) if assignee_name else []

        bot_logger.info(f"Creating task: project={pname}, name='{name[:50]}', prio={priority}, assignees={assignee_ids}, deadline={target_date}")

        result = await plane_api.create_issue(
            project_id=pid,
            name=name,
            priority=priority,
            assignees=assignee_ids or None,
            description=description,
            target_date=target_date,
        )

        if result:
            seq = result.get('sequence_id', '?')
            return f"✓ Создана {pname}-{seq}: {name}"
        return f"✗ Plane API вернул ошибку. Проект={pname}, имя='{name[:40]}'"

    except Exception as e:
        bot_logger.error(f"_handle_create_task_from_draft error: {e}", exc_info=True)
        return f"✗ Ошибка: {str(e)[:100]}"


def _find_project(projects: list, ident: str) -> dict | None:
    """Find project by identifier/name (exact then substring)."""
    ident_upper = ident.upper()
    # Exact match on identifier or name
    for p in projects:
        if ident_upper in (p.get('identifier', '').upper(), p.get('name', '').upper()):
            return p
    # Substring match
    for p in projects:
        if ident_upper in p.get('name', '').upper() or ident_upper in p.get('identifier', '').upper():
            return p
    return None


def _resolve_assignee_ids(assignee_name: str, members: list) -> list:
    """Resolve assignee name to list of member UUIDs."""
    if not assignee_name or not members:
        return []
    query = assignee_name.lower()
    for m in members:
        mname = m.display_name if hasattr(m, 'display_name') else m.get('display_name', '')
        first = m.first_name if hasattr(m, 'first_name') else m.get('first_name', '')
        if query in f"{first} {mname}".lower():
            mid = m.id if hasattr(m, 'id') else m.get('id')
            return [mid]
    return []


async def _send_confirmation(status_msg: Message, text: str, action: dict):
    """Show confirmation keyboard for write action."""
    act = action.get("action", "?")
    seq = action.get("seq_id", "?")

    labels = {
        "close_issue": f"Закрыть #{seq}",
        "assign_issue": f"Назначить #{seq} → {action.get('assignee', '?')}",
        "unassign_issue": f"Снять исполнителя #{seq}",
        "comment_issue": f"Коммент к #{seq}",
        "update_status": f"Статус #{seq} → {action.get('status', '?')}",
        "update_priority": f"Приоритет #{seq} → {action.get('priority', '?')}",
        "set_deadline": f"Дедлайн #{seq} → {action.get('target_date', '?')}",
        "set_start_date": f"Начало #{seq} → {action.get('start_date', '?')}",
        "rename_issue": f"Переименовать #{seq}",
        "set_description": f"Описание #{seq}",
        "archive_issue": f"Архивировать #{seq}",
        "create_task": f"Создать: {action.get('name', '?')[:30]}",
    }
    label = labels.get(act, act)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"✓ {label}", callback_data="plane_act:confirm"),
            InlineKeyboardButton(text="✗ Отмена", callback_data="plane_act:cancel"),
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

    if action_name == "create_task":
        result_text = await _handle_create_task(action)
    elif seq_id:
        found = await plane_service.find_issue_by_seq(seq_id)
        if not found:
            result_text = f"Задача #{seq_id} не найдена"
        else:
            project_id, pident, issue = found

            if action_name == "close_issue":
                ok = await plane_service.close_issue(project_id, issue["id"])
                if ok and action.get("comment"):
                    await plane_service.add_comment(project_id, issue["id"], action["comment"])
                if ok:
                    # Ask about archiving
                    await state.update_data(
                        pending_action=None,
                        archive_project_id=project_id,
                        archive_issue_id=issue["id"],
                        archive_seq_id=seq_id,
                    )
                    kb = InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="📦 Архивировать", callback_data="plane_act:archive_after"),
                        InlineKeyboardButton(text="Нет", callback_data="plane_act:skip_archive"),
                    ]])
                    await callback.message.edit_text(
                        f"<b>✓ Задача #{seq_id} закрыта</b>\n\nАрхивировать тоже?",
                        parse_mode="HTML", reply_markup=kb,
                    )
                    await callback.answer()
                    return
                else:
                    result_text = f"✗ Не удалось закрыть #{seq_id}"

            elif action_name == "assign_issue":
                assignee = action.get("assignee", "")
                name = await plane_service.assign_issue(project_id, issue["id"], assignee)
                result_text = f"✓ #{seq_id} → {name}" if name else f"✗ Не нашёл '{assignee}' в команде"

            elif action_name == "comment_issue":
                comment = action.get("comment", "")
                ok = await plane_service.add_comment(project_id, issue["id"], comment)
                result_text = f"✓ Комментарий к #{seq_id} добавлен" if ok else f"✗ Ошибка"

            elif action_name == "update_status":
                target_group = action.get("status", "")
                new_name = await plane_service.change_status(project_id, issue["id"], target_group)
                result_text = f"✓ #{seq_id} → {new_name}" if new_name else f"✗ Статус '{target_group}' не найден"

            elif action_name == "update_priority":
                prio = action.get("priority", "medium")
                ok = await plane_service.change_priority(project_id, issue["id"], prio)
                prio_label = PRIORITY_LABELS.get(prio, prio)
                result_text = f"✓ #{seq_id} приоритет → {prio_label}" if ok else f"✗ Ошибка смены приоритета"

            elif action_name == "set_deadline":
                target = action.get("target_date", "")
                ok = await plane_service.set_deadline(project_id, issue["id"], target)
                if ok:
                    result_text = f"✓ #{seq_id} дедлайн → {target}" if target else f"✓ #{seq_id} дедлайн убран"
                else:
                    result_text = f"✗ Ошибка установки дедлайна"

            elif action_name == "rename_issue":
                new_name = action.get("new_name", "")
                if not new_name:
                    result_text = "✗ Не указано новое название"
                else:
                    ok = await plane_service.rename_issue(project_id, issue["id"], new_name)
                    result_text = f"✓ #{seq_id} → {new_name}" if ok else f"✗ Ошибка переименования"

            elif action_name == "unassign_issue":
                ok = await plane_service.unassign_issue(project_id, issue["id"])
                result_text = f"✓ #{seq_id} исполнитель снят" if ok else f"✗ Ошибка"

            elif action_name == "archive_issue":
                ok = await plane_service.archive_issue(project_id, issue["id"])
                result_text = f"✓ #{seq_id} архивирована" if ok else f"✗ Ошибка архивации"

            elif action_name == "set_description":
                desc = action.get("description", "")
                if not desc:
                    result_text = "✗ Не указано описание"
                else:
                    ok = await plane_service.set_description(project_id, issue["id"], desc)
                    result_text = f"✓ #{seq_id} описание обновлено" if ok else f"✗ Ошибка"

            elif action_name == "set_start_date":
                start = action.get("start_date", "")
                ok = await plane_service.set_start_date(project_id, issue["id"], start)
                if ok:
                    result_text = f"✓ #{seq_id} начало → {start}" if start else f"✓ #{seq_id} дата начала убрана"
                else:
                    result_text = f"✗ Ошибка установки даты начала"

            else:
                result_text = f"✗ Действие '{action_name}' не поддерживается"
    else:
        if not seq_id and action_name != "create_task":
            result_text = f"✗ AI не указал номер задачи (seq_id). Уточни запрос, например: #123"

    await callback.message.edit_text(f"<b>{result_text}</b>", parse_mode="HTML")
    await state.set_state(PlaneAssistantStates.conversation)
    await state.update_data(pending_action=None)


async def _handle_create_task(action: dict) -> str:
    """Create a new task in Plane (legacy confirm path)."""
    project_ident = action.get("project", "")
    name = action.get("name", "")
    priority = action.get("priority", "none")
    assignee_name = action.get("assignee")

    if not project_ident or not name:
        return "✗ Не указан проект или название задачи"

    try:
        projects = await plane_api.get_all_projects()
        if not projects:
            return "✗ Не удалось загрузить проекты из Plane"

        project = _find_project(projects, project_ident)
        if not project:
            avail = ", ".join(p.get('identifier', '?') for p in projects[:10])
            return f"✗ Проект '{project_ident}' не найден. Есть: {avail}"

        pid = project['id']
        pname = project.get('identifier', '?')
        assignee_ids = _resolve_assignee_ids(assignee_name, await plane_api.get_workspace_members()) if assignee_name else []

        bot_logger.info(f"Creating task (confirm): project={pname}, name='{name[:50]}', prio={priority}")

        result = await plane_api.create_issue(
            project_id=pid,
            name=name,
            priority=priority,
            assignees=assignee_ids or None,
        )

        if result:
            seq = result.get('sequence_id', '?')
            return f"✓ Создана {pname}-{seq}: {name}"
        return f"✗ Plane API вернул ошибку. Проект={pname}, имя='{name[:40]}'"

    except Exception as e:
        bot_logger.error(f"_handle_create_task error: {e}", exc_info=True)
        return f"✗ Ошибка: {str(e)[:100]}"


@router.callback_query(F.data == "plane_act:cancel")
async def on_cancel(callback: CallbackQuery, state: FSMContext):
    """Cancel write action."""
    await state.update_data(pending_action=None)
    await state.set_state(PlaneAssistantStates.conversation)
    await callback.message.edit_text("Действие отменено.", parse_mode=None)
    await callback.answer()


@router.callback_query(F.data == "plane_act:archive_after")
async def on_archive_after_close(callback: CallbackQuery, state: FSMContext):
    """Archive issue after closing it."""
    data = await state.get_data()
    project_id = data.get("archive_project_id")
    issue_id = data.get("archive_issue_id")
    seq_id = data.get("archive_seq_id", "?")

    if not project_id or not issue_id:
        await callback.message.edit_text("<b>✗ Нет данных для архивации</b>", parse_mode="HTML")
        await callback.answer()
        return

    ok = await plane_service.archive_issue(project_id, issue_id)
    if ok:
        text = f"<b>✓ Задача #{seq_id} закрыта и архивирована</b>"
    else:
        text = f"<b>✓ Задача #{seq_id} закрыта</b>\n✗ Ошибка архивации"

    await state.update_data(archive_project_id=None, archive_issue_id=None, archive_seq_id=None)
    await state.set_state(PlaneAssistantStates.conversation)
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "plane_act:skip_archive")
async def on_skip_archive(callback: CallbackQuery, state: FSMContext):
    """Skip archiving after close."""
    seq_id = (await state.get_data()).get("archive_seq_id", "?")
    await state.update_data(archive_project_id=None, archive_issue_id=None, archive_seq_id=None)
    await state.set_state(PlaneAssistantStates.conversation)
    await callback.message.edit_text(f"<b>✓ Задача #{seq_id} закрыта</b>", parse_mode="HTML")
    await callback.answer()


# ---- Message editing helper ----

async def _safe_edit(msg: Message, text: str, **kwargs):
    """Edit message with HTML, fallback to plain text on parse error."""
    if not text:
        text = "(пустой ответ)"

    if len(text) > 4000:
        text = text[:3950] + "\n\n<i>...обрезано</i>"

    try:
        await msg.edit_text(text, parse_mode="HTML", **kwargs)
    except Exception:
        clean = re.sub(r'<[^>]+>', '', text)
        try:
            await msg.edit_text(clean[:4000], parse_mode=None, **kwargs)
        except Exception as e:
            bot_logger.error(f"Failed to edit message: {e}")
