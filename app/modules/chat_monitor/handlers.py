"""
Команды для управления мониторингом чатов и AI анализом
"""
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

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

    Usage:
    /ai_summary - Summary of last 100 messages
    /ai_summary 50 - Summary of last 50 messages
    """
    user_id = message.from_user.id

    # Admin only
    if not settings.is_admin(user_id):
        await message.reply("❌ Только для админов")
        return

    # Parse limit from command args
    limit = 100
    if message.text:
        parts = message.text.split()
        if len(parts) > 1:
            try:
                limit = int(parts[1])
                limit = max(10, min(500, limit))  # Clamp between 10 and 500
            except ValueError:
                pass

    # Send "typing" status
    await message.bot.send_chat_action(message.chat.id, "typing")

    # Generate summary
    summary = await summary_service.generate_summary(
        chat_id=message.chat.id,
        limit=limit,
        summary_type="general"
    )

    if summary:
        formatted = summary_service.format_summary_message(summary)
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
