#!/bin/bash

echo "🛠️ УПРОЩЕННОЕ ТЕСТИРОВАНИЕ - ОТКЛЮЧЕНИЕ ПРОБЛЕМНЫХ МОДУЛЕЙ"

# Создаем бэкап main.py 
cp app/main.py app/main.py.backup

# Временно отключаем work_journal модуль для тестирования daily_tasks
cat > app/main.py << 'EOF'
"""
Основной файл Telegram бота HHIVP IT Management - УПРОЩЕННАЯ ВЕРСИЯ ДЛЯ ТЕСТИРОВАНИЯ
"""
import asyncio
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy import text

from .config import settings
from .database.database import init_db, close_db
from .utils.logger import bot_logger, setup_logging
from .middleware.auth import AuthMiddleware
from .middleware.logging import LoggingMiddleware, GroupMonitoringMiddleware, PerformanceMiddleware
from .middleware.database import DatabaseSessionMiddleware

# ТОЛЬКО ТЕСТОВЫЕ МОДУЛИ 
from .modules.common import start
from .modules.daily_tasks import router as daily_tasks_router
# ВРЕМЕННО ОТКЛЮЧЕН: from .modules.work_journal import router as work_journal_router

from .services.daily_tasks_service import init_daily_tasks_service
from .services.scheduler import scheduler
from .modules.common.start import COMMANDS_MENU


async def setup_bot_commands(bot: Bot):
    """Настройка команд бота"""
    try:
        await bot.set_my_commands(COMMANDS_MENU)
        bot_logger.info("Bot commands menu set successfully")
    except Exception as e:
        bot_logger.error(f"Failed to set bot commands: {e}")


async def on_startup(bot: Bot):
    """Действия при запуске бота"""
    bot_logger.info("Bot startup initiated")
    
    try:
        # Инициализация базы данных
        await init_db()
        bot_logger.info("Database initialized")
        
        # Инициализация сервиса ежедневных задач
        await init_daily_tasks_service(bot)
        bot_logger.info("Daily tasks service initialized")
        
        # Запуск планировщика ежедневных задач
        if settings.daily_tasks_enabled:
            await scheduler.start()
            bot_logger.info("Daily tasks scheduler started")
        
        # Настройка команд бота
        await setup_bot_commands(bot)
        
        # Получаем информацию о боте
        bot_info = await bot.get_me()
        bot_logger.info(f"Bot started: @{bot_info.username} (ID: {bot_info.id})")
        
        # Уведомляем всех администраторов о запуске
        from datetime import datetime
        escaped_time = datetime.now().strftime("%d\\.%m\\.%Y %H:%M:%S")
        escaped_username = bot_info.username.replace('_', '\\_')
        
        startup_message = (
            "🟢 *ТЕСТОВАЯ ВЕРСИЯ\\! Daily Tasks Module тестирование*\\n\\n"
            f"🤖 *Username:* @{escaped_username}\\n"
            f"🆔 *Bot ID:* {bot_info.id}\\n"
            f"📊 *Версия:* REFACTORING TEST\\n"
            f"🕐 *Время запуска:* {escaped_time}\\n\\n"
            f"📧 *ТЕСТ:* Отправьте zarudesu@gmail\\.com для проверки email обработки"
        )
        
        for admin_id in settings.admin_user_id_list:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=startup_message,
                    parse_mode="MarkdownV2"
                )
            except Exception as e:
                bot_logger.warning(f"Could not notify admin {admin_id} about startup: {e}")
            
    except Exception as e:
        bot_logger.error(f"Startup failed: {e}")
        raise


async def on_shutdown(bot: Bot):
    """Действия при завершении работы бота"""
    bot_logger.info("Bot shutdown initiated")
    
    try:
        # Остановка планировщика
        if scheduler.is_running():
            await scheduler.stop()
            bot_logger.info("Daily tasks scheduler stopped")
        
        # Закрываем подключение к базе данных
        await close_db()
        bot_logger.info("Database connection closed")
        
    except Exception as e:
        bot_logger.error(f"Shutdown error: {e}")
    
    bot_logger.info("Bot shutdown completed")


async def main():
    """Основная функция запуска бота"""
    
    # Настройка логирования
    setup_logging()
    bot_logger.info("Starting HHIVP IT Assistant Bot - TESTING VERSION")
    
    try:
        # Создание бота и диспетчера
        bot = Bot(
            token=settings.telegram_token,
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2)
        )
        
        dp = Dispatcher()
        
        # Регистрация middleware (порядок важен!)
        dp.message.middleware(DatabaseSessionMiddleware())
        dp.callback_query.middleware(DatabaseSessionMiddleware())
        dp.message.middleware(PerformanceMiddleware())
        dp.callback_query.middleware(PerformanceMiddleware())
        dp.message.middleware(LoggingMiddleware())
        dp.callback_query.middleware(LoggingMiddleware())
        dp.message.middleware(GroupMonitoringMiddleware())
        dp.message.middleware(AuthMiddleware())
        dp.callback_query.middleware(AuthMiddleware())
        
        # Регистрация роутеров в ТЕСТОВОМ порядке:
        dp.include_router(start.router)
        bot_logger.info("✅ Common module loaded (start, help, profile)")
        
        dp.include_router(daily_tasks_router.router)
        bot_logger.info("✅ Daily Tasks module loaded (PRIORITY: email handlers)")
        
        # WORK JOURNAL ВРЕМЕННО ОТКЛЮЧЕН
        bot_logger.info("⚠️ Work Journal module DISABLED for testing")
        
        bot_logger.info("🎯 TESTING VERSION: Email isolation test ready")
        
        # Регистрация событий жизненного цикла
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)
        
        bot_logger.info("Bot configuration completed, starting polling...")
        
        # Запуск бота
        await dp.start_polling(
            bot,
            allowed_updates=["message", "callback_query", "inline_query"],
            drop_pending_updates=True
        )
        
    except KeyboardInterrupt:
        bot_logger.info("Bot stopped by user")
    except Exception as e:
        bot_logger.error(f"Bot crashed: {e}")
        raise
    finally:
        bot_logger.info("Bot terminated")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 Bot crashed: {e}")
        sys.exit(1)
EOF

echo "✅ Создана упрощенная версия main.py для тестирования"
echo "📧 Теперь можно тестировать email обработку без work_journal конфликтов"
echo ""
echo "🔄 Для запуска используйте:"
echo "docker-compose up telegram-bot --build"
