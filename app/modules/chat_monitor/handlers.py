"""
Команды для управления мониторингом чатов и AI анализом

Thread Mapping Commands (for admins):
- /link_thread <client_chat_id> <client_name> - Link current thread to client chat
- /threads - List all thread mappings
- /unlink_thread - Remove mapping for current thread

AI Commands (work in threads - fetch context from CLIENT chat):
- /ai_summary - Summary of client chat (when in mapped thread)
- /ai_daily - Daily summary
- /ai_problems - Detected issues
"""
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from typing import Optional

from ...config import settings
from ...services.summary_service import summary_service
from ...services.chat_context_service import chat_context_service
from ...utils.logger import bot_logger

router = Router()


@router.message(Command("monitor_start"))
async def monitor_start_command(message: Message):
    """Включить мониторинг чата"""
    user_id = message.from_user.id

    if not settings.is_admin(user_id):
        await message.reply("❌ Только для админов")
        return

    # TODO: Включить мониторинг для этого чата
    await message.reply(
        "✅ *Мониторинг чата включен*\n\n"
        "Бот будет:\n"
        "• Читать все сообщения\n"
        "• Анализировать контекст для AI\n"
        "• Автоматически создавать задачи\n"
        "• Реагировать на триггеры",
        parse_mode="Markdown"
    )


@router.message(Command("monitor_stop"))
async def monitor_stop_command(message: Message):
    """Выключить мониторинг чата"""
    user_id = message.from_user.id

    if not settings.is_admin(user_id):
        await message.reply("❌ Только для админов")
        return

    await message.reply("🛑 Мониторинг чата остановлен")


@router.message(Command("monitor_status"))
async def monitor_status_command(message: Message):
    """Статус мониторинга"""
    chat_id = message.chat.id

    # Get actual stats
    try:
        message_count = await chat_context_service.get_message_count(chat_id)
        pending_issues = await chat_context_service.get_pending_issues(chat_id)
        settings_obj = await chat_context_service.get_chat_settings(chat_id)

        problem_detection = "✅" if (settings_obj and settings_obj.problem_detection_enabled) else "❌"
        daily_summary = "✅" if (settings_obj and settings_obj.daily_summary_enabled) else "❌"

        await message.reply(
            f"📊 <b>Статус мониторинга</b>\n\n"
            f"• Сообщений в БД: {message_count}\n"
            f"• Открытых проблем: {len(pending_issues)}\n"
            f"• Детекция проблем: {problem_detection}\n"
            f"• Дневные сводки: {daily_summary}",
            parse_mode="HTML"
        )
    except Exception as e:
        bot_logger.error(f"Error getting monitor status: {e}")
        await message.reply(
            "📊 <b>Статус мониторинга</b>\n\n"
            "• Статус: Активен\n"
            "• Ошибка получения статистики",
            parse_mode="HTML"
        )


# ===================== AI COMMANDS =====================

@router.message(Command("ai_summary"))
async def ai_summary_command(message: Message):
    """
    Generate AI summary of recent chat discussion.

    Usage in WORK GROUP THREAD (mapped to client):
    /ai_summary - Summary of CLIENT'S chat (last 100 messages)
    /ai_summary 50 - Summary of last 50 messages from client chat

    Usage in CLIENT CHAT (direct):
    /ai_summary - Summary of this chat

    Usage in PM with client name:
    /ai_summary DELTA - Summary of DELTA's chat
    """
    user_id = message.from_user.id

    # Admin only
    if not settings.is_admin(user_id):
        await message.reply("❌ Только для админов")
        return

    # Parse args
    limit = 100
    client_name_arg = None

    if message.text:
        parts = message.text.split()
        for part in parts[1:]:
            try:
                limit = int(part)
                limit = max(10, min(500, limit))
            except ValueError:
                # Not a number - might be client name
                client_name_arg = part

    # Determine target chat
    thread_id = getattr(message, 'message_thread_id', None)
    target_chat_id = message.chat.id
    client_name = None

    # Check if we're in a mapped thread
    if thread_id:
        mapping = await chat_context_service.get_mapping_by_thread(
            thread_id=thread_id,
            work_group_id=message.chat.id
        )
        if mapping:
            target_chat_id = mapping.client_chat_id
            client_name = mapping.client_name
            bot_logger.info(f"AI Summary: Using mapped client {client_name} (chat {target_chat_id})")

    # Or check if client name provided as argument
    if client_name_arg and not client_name:
        mapping = await chat_context_service.get_mapping_by_client(client_name_arg.upper())
        if mapping:
            target_chat_id = mapping.client_chat_id
            client_name = mapping.client_name
            bot_logger.info(f"AI Summary: Using client {client_name} from arg (chat {target_chat_id})")
        else:
            await message.reply(f"❌ Клиент <b>{client_name_arg}</b> не найден в маппинге", parse_mode="HTML")
            return

    # Send "typing" status
    await message.bot.send_chat_action(message.chat.id, "typing")

    # Generate summary
    summary = await summary_service.generate_summary(
        chat_id=target_chat_id,
        limit=limit,
        summary_type="general"
    )

    if summary:
        formatted = summary_service.format_summary_message(summary)
        if client_name:
            header = f"📊 <b>Резюме чата клиента {client_name}</b>\n\n"
            formatted = header + formatted
        await message.reply(formatted, parse_mode="HTML")
    else:
        await message.reply(
            "❌ <b>Не удалось создать резюме</b>\n\n"
            "Возможные причины:\n"
            "• Недостаточно сообщений (нужно минимум 10)\n"
            "• Ошибка AI сервиса",
            parse_mode="HTML"
        )


@router.message(Command("ai_daily"))
async def ai_daily_command(message: Message):
    """
    Generate daily summary for today.

    Usage:
    /ai_daily - Summary of today's discussion
    """
    user_id = message.from_user.id

    if not settings.is_admin(user_id):
        await message.reply("❌ Только для админов")
        return

    await message.bot.send_chat_action(message.chat.id, "typing")

    summary = await summary_service.generate_daily_summary(
        chat_id=message.chat.id
    )

    if summary:
        formatted = "📅 <b>Дневная сводка</b>\n\n" + summary_service.format_summary_message(summary)
        await message.reply(formatted, parse_mode="HTML")
    else:
        await message.reply(
            "❌ Недостаточно сообщений для дневной сводки",
            parse_mode="HTML"
        )


@router.message(Command("ai_problems"))
async def ai_problems_command(message: Message):
    """
    Show detected problems/issues in this chat.

    Usage:
    /ai_problems - List open issues
    """
    user_id = message.from_user.id

    if not settings.is_admin(user_id):
        await message.reply("❌ Только для админов")
        return

    issues = await chat_context_service.get_pending_issues(message.chat.id)

    if not issues:
        await message.reply(
            "✅ <b>Нет открытых проблем</b>\n\n"
            "Все обнаруженные проблемы решены или их не было.",
            parse_mode="HTML"
        )
        return

    lines = ["📋 <b>Открытые проблемы</b>\n"]

    for issue in issues[:10]:  # Show max 10
        type_emoji = {
            "urgent": "🚨",
            "problem": "⚠️",
            "question": "❓",
            "complaint": "😤"
        }
        emoji = type_emoji.get(issue.issue_type, "📋")

        created = issue.created_at.strftime("%d.%m %H:%M") if issue.created_at else "?"
        title = issue.title[:50] + "..." if len(issue.title or "") > 50 else (issue.title or "Без названия")

        lines.append(f"{emoji} [{created}] {title}")
        lines.append(f"   Статус: {issue.status} | ID: {issue.id}")
        lines.append("")

    if len(issues) > 10:
        lines.append(f"<i>... и ещё {len(issues) - 10} проблем</i>")

    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("ai_settings"))
async def ai_settings_command(message: Message):
    """
    Show/update AI settings for this chat.

    Usage:
    /ai_settings - Show current settings
    /ai_settings problem_detection on/off
    /ai_settings daily_summary on/off
    /ai_settings context_size 100
    """
    user_id = message.from_user.id

    if not settings.is_admin(user_id):
        await message.reply("❌ Только для админов")
        return

    chat_id = message.chat.id
    parts = message.text.split() if message.text else []

    # Get or create settings
    chat_settings = await chat_context_service.get_or_create_settings(
        chat_id=chat_id,
        chat_title=message.chat.title
    )

    # Parse commands
    if len(parts) >= 3:
        setting_name = parts[1].lower()
        setting_value = parts[2].lower()

        try:
            if setting_name == "problem_detection":
                enabled = setting_value in ("on", "true", "1", "да")
                await chat_context_service.update_settings(
                    chat_id, problem_detection_enabled=enabled
                )
                await message.reply(f"✅ Детекция проблем: {'включена' if enabled else 'выключена'}")
                return

            elif setting_name == "daily_summary":
                enabled = setting_value in ("on", "true", "1", "да")
                await chat_context_service.update_settings(
                    chat_id, daily_summary_enabled=enabled
                )
                await message.reply(f"✅ Дневные сводки: {'включены' if enabled else 'выключены'}")
                return

            elif setting_name == "context_size":
                size = int(setting_value)
                size = max(10, min(500, size))
                await chat_context_service.update_settings(
                    chat_id, context_size=size
                )
                await message.reply(f"✅ Размер контекста: {size} сообщений")
                return

        except Exception as e:
            await message.reply(f"❌ Ошибка: {e}")
            return

    # Show current settings
    pd = "✅" if chat_settings.problem_detection_enabled else "❌"
    ds = "✅" if chat_settings.daily_summary_enabled else "❌"
    ctx = chat_settings.context_size

    await message.reply(
        f"⚙️ <b>Настройки AI для чата</b>\n\n"
        f"<b>Детекция проблем:</b> {pd}\n"
        f"<b>Дневные сводки:</b> {ds}\n"
        f"<b>Размер контекста:</b> {ctx} сообщений\n\n"
        f"<i>Изменить:</i>\n"
        f"<code>/ai_settings problem_detection on/off</code>\n"
        f"<code>/ai_settings daily_summary on/off</code>\n"
        f"<code>/ai_settings context_size 100</code>",
        parse_mode="HTML"
    )


# ===================== THREAD MAPPING COMMANDS =====================

@router.message(Command("link_thread"))
async def link_thread_command(message: Message):
    """
    Link current thread to a client chat.

    Usage (in a thread):
    /link_thread <client_chat_id> <client_name>

    Example:
    /link_thread -1001234567890 DELTA
    """
    user_id = message.from_user.id

    if not settings.is_admin(user_id):
        await message.reply("❌ Только для админов")
        return

    # Must be in a thread
    thread_id = getattr(message, 'message_thread_id', None)
    if not thread_id:
        await message.reply(
            "❌ <b>Эта команда работает только в треде</b>\n\n"
            "Перейдите в тред (topic) рабочей группы и выполните команду там.",
            parse_mode="HTML"
        )
        return

    # Parse arguments
    parts = message.text.split() if message.text else []
    if len(parts) < 3:
        await message.reply(
            "❌ <b>Неверный формат</b>\n\n"
            "Использование:\n"
            "<code>/link_thread &lt;client_chat_id&gt; &lt;client_name&gt;</code>\n\n"
            "Пример:\n"
            "<code>/link_thread -1001234567890 DELTA</code>\n\n"
            "Чтобы узнать chat_id клиента, перешлите сообщение из его чата боту @userinfobot",
            parse_mode="HTML"
        )
        return

    try:
        client_chat_id = int(parts[1])
        client_name = parts[2].upper()
    except ValueError:
        await message.reply("❌ client_chat_id должен быть числом")
        return

    # Check if mapping already exists
    existing = await chat_context_service.get_mapping_by_thread(thread_id, message.chat.id)
    if existing:
        await message.reply(
            f"⚠️ Этот тред уже привязан к клиенту <b>{existing.client_name}</b>\n\n"
            f"Используйте /unlink_thread чтобы удалить привязку",
            parse_mode="HTML"
        )
        return

    # Create mapping
    mapping = await chat_context_service.create_thread_mapping(
        work_group_id=message.chat.id,
        thread_id=thread_id,
        client_chat_id=client_chat_id,
        client_name=client_name,
        thread_name=None,  # TODO: get thread name from Telegram API
        created_by=user_id
    )

    await message.reply(
        f"✅ <b>Тред привязан к клиенту</b>\n\n"
        f"• Клиент: <b>{client_name}</b>\n"
        f"• Chat ID клиента: <code>{client_chat_id}</code>\n"
        f"• Thread ID: <code>{thread_id}</code>\n\n"
        f"Теперь /ai_summary в этом треде будет показывать резюме из чата клиента.",
        parse_mode="HTML"
    )


@router.message(Command("threads"))
async def threads_command(message: Message):
    """
    List all thread-to-client mappings.

    Usage:
    /threads - Show all mappings
    """
    user_id = message.from_user.id

    if not settings.is_admin(user_id):
        await message.reply("❌ Только для админов")
        return

    mappings = await chat_context_service.get_all_mappings()

    if not mappings:
        await message.reply(
            "📋 <b>Нет привязок тредов к клиентам</b>\n\n"
            "Используйте /link_thread в треде чтобы создать привязку.",
            parse_mode="HTML"
        )
        return

    lines = ["📋 <b>Привязки тредов к клиентам</b>\n"]

    for m in mappings:
        lines.append(
            f"• <b>{m.client_name}</b>\n"
            f"  Thread: <code>{m.thread_id}</code>\n"
            f"  Client chat: <code>{m.client_chat_id}</code>"
        )
        lines.append("")

    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("unlink_thread"))
async def unlink_thread_command(message: Message):
    """
    Remove thread-to-client mapping.

    Usage (in a thread):
    /unlink_thread - Remove mapping for current thread
    """
    user_id = message.from_user.id

    if not settings.is_admin(user_id):
        await message.reply("❌ Только для админов")
        return

    thread_id = getattr(message, 'message_thread_id', None)
    if not thread_id:
        await message.reply(
            "❌ <b>Эта команда работает только в треде</b>\n\n"
            "Перейдите в тред и выполните команду там.",
            parse_mode="HTML"
        )
        return

    mapping = await chat_context_service.get_mapping_by_thread(thread_id, message.chat.id)
    if not mapping:
        await message.reply("❌ Этот тред не привязан к клиенту")
        return

    client_name = mapping.client_name
    await chat_context_service.delete_mapping(mapping.id)

    await message.reply(
        f"✅ Привязка к клиенту <b>{client_name}</b> удалена",
        parse_mode="HTML"
    )
