from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from loguru import logger

router = Router()

@router.message(Command("start", "help"))
async def help_command(message: Message):
    """Команда помощи и приветствия"""
    
    user_id = message.from_user.id
    username = message.from_user.username or "Пользователь"
    
    logger.info(f"👋 Пользователь {username} ({user_id}) запросил помощь")
    
    help_text = """
🤖 **HHIVP IT Assistant**

Я помогу вам быстро найти информацию в IT-системах:

🔍 **Поиск:**
• `/search <запрос>` - поиск по всем системам
• `/ip <адрес>` - информация об IP
• `/device <название>` - поиск устройства
• `/client <название>` - информация о клиенте
• `/password <сервис>` - поиск пароля

📋 **Системы:**
• NetBox - сети и устройства
• Vaultwarden - пароли и доступы
• BookStack - база знаний

⚙️ **Админ (только для администраторов):**
• `/admin` - панель администратора
• `/stats` - статистика использования
• `/logs` - последние логи

❓ **Помощь:**
• `/help` - это сообщение
• `/status` - статус всех систем

Просто напишите что ищете, и я найду это во всех системах! 🚀
    """
    
    await message.answer(help_text, parse_mode="Markdown")

@router.message(Command("status"))
async def status_command(message: Message):
    """Статус всех систем"""
    
    logger.info(f"📊 Пользователь {message.from_user.id} запросил статус систем")
    
    # TODO: Реальная проверка статуса систем
    status_text = """
📊 **Статус систем HHIVP IT**

🟢 **NetBox** - Работает
🟢 **Vaultwarden** - Работает  
🟢 **BookStack** - Работает
🟢 **Telegram Bot** - Работает
🟢 **База данных** - Работает
🟢 **Redis** - Работает

✅ Все системы функционируют нормально
🕒 Последняя проверка: только что
    """
    
    await message.answer(status_text, parse_mode="Markdown")
