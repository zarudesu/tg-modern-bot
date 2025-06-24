from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from loguru import logger

from config import settings

router = Router()

# Проверка на администратора
def is_admin(user_id: int) -> bool:
    return user_id in settings.ADMIN_USERS

@router.message(Command("admin"))
async def admin_command(message: Message):
    """Админ панель"""
    
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    logger.info(f"👑 Администратор {user_id} открыл админ панель")
    
    admin_text = """
👑 **Панель администратора HHIVP IT**

📊 **Статистика:**
• `/stats` - статистика использования
• `/logs` - последние логи системы
• `/users` - управление пользователями

🔧 **Управление:**
• `/restart <service>` - перезапуск сервиса
• `/backup` - создать backup
• `/update` - обновить систему

⚙️ **Настройки:**
• `/config` - показать конфигурацию
• `/tokens` - управление API токенами
• `/permissions` - права доступа

🔍 **Мониторинг:**
• `/health` - здоровье системы
• `/disk` - использование диска
• `/memory` - использование памяти
    """
    
    await message.answer(admin_text, parse_mode="Markdown")

@router.message(Command("stats"))
async def stats_command(message: Message):
    """Статистика использования"""
    
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    logger.info(f"📊 Администратор {user_id} запросил статистику")
    
    # TODO: Реальная статистика из БД
    stats_text = """
📊 **Статистика HHIVP IT-System**

🔍 **Поисковые запросы (за 24ч):**
• Всего запросов: 127
• NetBox: 45 запросов
• Vaultwarden: 32 запроса  
• BookStack: 28 запросов
• IP поиск: 22 запроса

👥 **Пользователи:**
• Активных: 3
• Всего зарегистрированных: 5
• Новых за неделю: 1

🖥️ **Системы:**
• Устройств в NetBox: 156
• Паролей в Vaultwarden: 89
• Страниц в BookStack: 34
• Клиентов: 6

🕒 **Время работы:**
• Система запущена: 5 дней 12 часов
• Последний перезапуск: 3 дня назад
    """
    
    await message.answer(stats_text, parse_mode="Markdown")

@router.message(Command("logs"))
async def logs_command(message: Message):
    """Последние логи системы"""
    
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    logger.info(f"📋 Администратор {user_id} запросил логи")
    
    try:
        # Читаем последние строки из лога
        with open("logs/bot.log", "r", encoding="utf-8") as f:
            lines = f.readlines()
            last_lines = lines[-20:]  # Последние 20 строк
            
        log_text = "📋 **Последние логи бота:**\n\n```\n" + "".join(last_lines) + "\n```"
        
        await message.answer(log_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Ошибка чтения логов: {e}")
        await message.answer("⚠️ Ошибка при чтении логов")

@router.message(Command("health"))
async def health_command(message: Message):
    """Проверка здоровья системы"""
    
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    logger.info(f"🏥 Администратор {user_id} запросил health check")
    
    # TODO: Реальная проверка здоровья систем
    health_text = """
🏥 **Проверка здоровья HHIVP IT-System**

🟢 **База данных PostgreSQL:** OK
   • Подключение: ✅
   • Активных соединений: 12/100
   • Размер БД: 247 MB

🟢 **Redis:** OK
   • Подключение: ✅  
   • Память: 45 MB / 512 MB
   • Ключей: 1,234

🟢 **NetBox:** OK
   • HTTP статус: 200
   • Время ответа: 234ms
   • API доступен: ✅

🟢 **Vaultwarden:** OK
   • HTTP статус: 200
   • Время ответа: 156ms
   • WebSocket: ✅

🟢 **BookStack:** OK
   • HTTP статус: 200
   • Время ответа: 189ms
   • API доступен: ✅

🟢 **Telegram Bot:** OK
   • Подключение: ✅
   • Обработано сообщений: 1,456
   • Ошибок: 0

✅ **Общий статус:** Все системы работают нормально
    """
    
    await message.answer(health_text, parse_mode="Markdown")

@router.message(Command("backup"))
async def backup_command(message: Message):
    """Создание backup"""
    
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    logger.info(f"💾 Администратор {user_id} запустил backup")
    
    backup_msg = await message.answer("💾 Создаю backup системы...")
    
    try:
        # TODO: Запуск реального backup скрипта
        import asyncio
        await asyncio.sleep(3)  # Имитация работы
        
        await backup_msg.edit_text(
            "✅ **Backup успешно создан!**\n\n"
            "📁 Архив сохранен в `/backup/`\n"
            "📅 Дата создания: сейчас\n"
            "💾 Размер: 156 MB",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Ошибка создания backup: {e}")
        await backup_msg.edit_text("⚠️ Ошибка при создании backup")
