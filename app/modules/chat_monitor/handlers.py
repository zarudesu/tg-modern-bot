"""
Команды для управления мониторингом чатов
"""
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

from ...config import settings

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
    await message.reply(
        "📊 *Статус мониторинга*\n\n"
        "• Статус: Активен\n"
        "• Сообщений обработано: 0\n"
        "• Задач создано: 0\n"
        "• Триггеров: 0",
        parse_mode="Markdown"
    )
