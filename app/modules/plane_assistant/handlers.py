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
5. Для действий — СНАЧАЛА текст, ПОТОМ один JSON-блок:
   {{"action": "close_issue", "seq_id": 123, "comment": "optional"}}
   {{"action": "assign_issue", "seq_id": 123, "assignee": "Тимофей"}}
   {{"action": "comment_issue", "seq_id": 123, "comment": "текст"}}
   {{"action": "create_task", "project": "HARZL", "name": "Название задачи", "priority": "high", "assignee": "Тимофей"}}
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
    # Try ```json block
    match = re.search(r'```json\s*(\{[^}]+\})\s*```', ai_text)
    if match:
        try:
            action = json.loads(match.group(1))
            clean = ai_text[:match.start()].strip()
            return clean, action
        except json.JSONDecodeError:
            pass

    # Try inline JSON with "action" key
    match2 = re.search(r'\{"action"\s*:\s*"[^"]+?"[^}]*\}', ai_text)
    if match2:
        try:
            action = json.loads(match2.group(0))
            clean = ai_text[:match2.start()].strip()
            return clean, action
        except json.JSONDecodeError:
            pass

    return ai_text, None


def _classify_query(msg: str) -> str:
    """Classify query complexity: 'action' (simple) or 'analysis' (needs smart model)."""
    msg_lower = msg.lower()
    action_kw = ['закрой', 'назначь', 'коммент', 'создай', 'удали', 'close', 'assign']
    if re.search(r'#\d+', msg) and any(kw in msg_lower for kw in action_kw):
        return "action"
    return "analysis"


def _get_provider_order(query_type: str) -> list:
    """Get provider priority based on query complexity.

    Analysis queries → Groq (70B, smart) first.
    Simple actions → OpenRouter (fast, free) first, Groq fallback.
    """
    if query_type == "action":
        return ["openrouter", "groq"]
    return ["groq", "openrouter"]


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
    kw_status = ['статус', 'status', 'обзор', 'сводк', 'итог']

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
        if not text:
            seq = action.get("seq_id", "?")
            act = action.get("action", "")
            fallbacks = {
                "close_issue": f"Закрываю задачу <b>#{seq}</b>",
                "assign_issue": f"Назначаю <b>#{seq}</b> на {action.get('assignee', '?')}",
                "comment_issue": f"Добавляю комментарий к <b>#{seq}</b>",
                "create_task": f"Создаю задачу: <b>{action.get('name', '?')}</b>",
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
        result = await _process_message(message.text, message.from_user.id, state, status_msg=status)
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

async def _send_confirmation(status_msg: Message, text: str, action: dict):
    """Show confirmation keyboard for write action."""
    act = action.get("action", "?")
    seq = action.get("seq_id", "?")

    labels = {
        "close_issue": f"Закрыть #{seq}",
        "assign_issue": f"Назначить #{seq} → {action.get('assignee', '?')}",
        "comment_issue": f"Коммент к #{seq}",
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
                result_text = f"✓ Задача #{seq_id} закрыта" if ok else f"✗ Не удалось закрыть #{seq_id}"
                if ok and action.get("comment"):
                    await plane_service.add_comment(project_id, issue["id"], action["comment"])

            elif action_name == "assign_issue":
                assignee = action.get("assignee", "")
                name = await plane_service.assign_issue(project_id, issue["id"], assignee)
                result_text = f"✓ #{seq_id} → {name}" if name else f"✗ Не нашёл '{assignee}' в команде"

            elif action_name == "comment_issue":
                comment = action.get("comment", "")
                ok = await plane_service.add_comment(project_id, issue["id"], comment)
                result_text = f"✓ Комментарий к #{seq_id} добавлен" if ok else f"✗ Ошибка"

    await callback.message.edit_text(f"<b>{result_text}</b>", parse_mode="HTML")
    await state.set_state(PlaneAssistantStates.conversation)
    await state.update_data(pending_action=None)


async def _handle_create_task(action: dict) -> str:
    """Create a new task in Plane."""
    project_ident = action.get("project", "")
    name = action.get("name", "")
    priority = action.get("priority", "none")
    assignee_name = action.get("assignee")

    if not project_ident or not name:
        return "✗ Не указан проект или название задачи"

    # Find project
    projects = await plane_api.get_all_projects()
    project = None
    ident_upper = project_ident.upper()
    for p in (projects or []):
        if ident_upper in (p.get('identifier', '').upper(), p.get('name', '').upper()):
            project = p
            break

    if not project:
        # Try fuzzy
        for p in (projects or []):
            if ident_upper in p.get('name', '').upper() or ident_upper in p.get('identifier', '').upper():
                project = p
                break

    if not project:
        return f"✗ Проект '{project_ident}' не найден"

    pid = project['id']

    # Resolve assignee
    assignee_ids = []
    if assignee_name:
        members = await plane_api.get_workspace_members()
        for m in (members or []):
            mname = m.display_name if hasattr(m, 'display_name') else m.get('display_name', '')
            first = m.first_name if hasattr(m, 'first_name') else m.get('first_name', '')
            if assignee_name.lower() in f"{first} {mname}".lower():
                mid = m.id if hasattr(m, 'id') else m.get('id')
                assignee_ids = [mid]
                break

    result = await plane_api.create_issue(
        project_id=pid,
        name=name,
        priority=priority,
        assignees=assignee_ids or None,
    )

    if result:
        seq = result.get('sequence_id', '?')
        pname = project.get('identifier', '?')
        return f"✓ Создана {pname}-{seq}: {name}"
    return "✗ Ошибка при создании задачи"


@router.callback_query(F.data == "plane_act:cancel")
async def on_cancel(callback: CallbackQuery, state: FSMContext):
    """Cancel write action."""
    await state.update_data(pending_action=None)
    await state.set_state(PlaneAssistantStates.conversation)
    await callback.message.edit_text("Действие отменено.", parse_mode=None)
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
