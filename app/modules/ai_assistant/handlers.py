"""
Команды для AI Assistant
"""
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

from ...core.ai.ai_manager import ai_manager
from ...core.ai.base import AIMessage, AIRole
from ...utils.logger import bot_logger

router = Router()


@router.message(Command("ai"))
async def ai_command(message: Message):
    """Команда для общения с AI"""
    user_id = message.from_user.id
    text = message.text.replace("/ai", "").strip()

    if not text:
        await message.reply(
            "🤖 *AI Ассистент*\n\n"
            "Используйте: `/ai ваш вопрос`\n\n"
            "Примеры:\n"
            "• `/ai расскажи о проекте`\n"
            "• `/ai создай задачу для новой фичи`\n"
            "• `/ai сделай суммари последних сообщений`",
            parse_mode="Markdown"
        )
        return

    # Показываем что бот думает
    thinking_msg = await message.reply("🤔 Думаю...")

    try:
        # Получаем ответ от AI
        response = await ai_manager.chat(
            user_message=text,
            system_prompt=(
                "Ты - AI ассистент для Telegram бота управления проектами. "
                "Ты помогаешь пользователям с задачами, проектами и вопросами. "
                "Отвечай кратко и по делу. Используй markdown для форматирования."
            )
        )

        # Обновляем сообщение с ответом
        await thinking_msg.edit_text(
            f"🤖 *AI Ассистент:*\n\n{response.content}\n\n"
            f"_Модель: {response.model} | Токенов: {response.tokens_used}_",
            parse_mode="Markdown"
        )

        bot_logger.info(
            f"AI response generated for user {user_id}",
            extra={
                "model": response.model,
                "tokens": response.tokens_used,
                "time": response.processing_time
            }
        )

    except Exception as e:
        bot_logger.error(f"AI command error: {e}")
        await thinking_msg.edit_text(
            "❌ Произошла ошибка при обращении к AI.\n"
            f"Ошибка: {str(e)}",
            parse_mode="Markdown"
        )


# NOTE: /ai_summary is implemented in chat_monitor/handlers.py with full thread mapping support


@router.message(Command("ai_auto_task"))
async def ai_auto_task_command(message: Message):
    """Включить автоматическое создание задач"""
    await message.reply(
        "🎯 *Автоматическое создание задач*\n\n"
        "AI будет автоматически определять задачи из сообщений в чате "
        "и предлагать создать их в Plane.\n\n"
        "_В разработке..._",
        parse_mode="Markdown"
    )


@router.message(Command("ai_help"))
async def ai_help_command(message: Message):
    """Справка по AI функциям"""
    help_text = """
🤖 *AI Ассистент - Справка*

*Доступные команды:*

`/ai <вопрос>` - Задать вопрос AI
`/ai_summary` - Создать суммари чата
`/ai_auto_task` - Авто-создание задач
`/ai_help` - Эта справка

*Возможности AI:*
• Ответы на вопросы
• Анализ текста
• Создание задач
• Суммаризация обсуждений
• Извлечение информации

*Примеры использования:*
```
/ai что делать дальше по проекту?
/ai создай задачу для деплоя
/ai проанализируй последние обсуждения
```
"""
    await message.reply(help_text, parse_mode="Markdown")
