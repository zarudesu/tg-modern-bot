"""
Основной файл Telegram бота HHIVP IT Management
"""
import asyncio
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from .config import settings
from .database.database import init_db, close_db
from .utils.logger import bot_logger, setup_logging
from .middleware.auth import AuthMiddleware
from .middleware.logging import LoggingMiddleware, GroupMonitoringMiddleware, PerformanceMiddleware
from .handlers import start
from .handlers.start import COMMANDS_MENU


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
        
        # Настройка команд бота
        await setup_bot_commands(bot)
        
        # Получаем информацию о боте
        bot_info = await bot.get_me()
        bot_logger.info(f"Bot started: @{bot_info.username} (ID: {bot_info.id})")
        
        # Уведомляем администратора о запуске
        try:
            await bot.send_message(
                chat_id=settings.admin_user_id,
                text="🟢 *HHIVP IT Bot запущен успешно\\!*\n\n"
                     f"🤖 *Username:* @{bot_info.username}\n"
                     f"🆔 *Bot ID:* {bot_info.id}\n"
                     f"📊 *Версия:* 1\\.0\\.0\n"
                     f"🕐 *Время запуска:* {asyncio.get_event_loop().time():.0f}",
                parse_mode="MarkdownV2"
            )
        except Exception as e:
            bot_logger.warning(f"Could not notify admin about startup: {e}")
            
    except Exception as e:
        bot_logger.error(f"Startup failed: {e}")
        raise


async def on_shutdown(bot: Bot):
    """Действия при завершении работы бота"""
    bot_logger.info("Bot shutdown initiated")
    
    try:
        # Уведомляем администратора о завершении
        try:
            await bot.send_message(
                chat_id=settings.admin_user_id,
                text="🔴 *HHIVP IT Bot завершает работу\\.*\n\n"
                     "🛑 Все процессы будут остановлены\\.",
                parse_mode="MarkdownV2"
            )
        except Exception as e:
            bot_logger.warning(f"Could not notify admin about shutdown: {e}")
        
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
    bot_logger.info("Starting HHIVP IT Management Bot")
    
    try:
        # Создание бота и диспетчера
        bot = Bot(
            token=settings.telegram_token,
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2)
        )
        
        dp = Dispatcher()
        
        # Регистрация middleware (порядок важен!)
        dp.message.middleware(PerformanceMiddleware())
        dp.callback_query.middleware(PerformanceMiddleware())
        
        dp.message.middleware(LoggingMiddleware())
        dp.callback_query.middleware(LoggingMiddleware())
        
        dp.message.middleware(GroupMonitoringMiddleware())
        
        dp.message.middleware(AuthMiddleware())
        dp.callback_query.middleware(AuthMiddleware())
        
        # Регистрация роутеров
        dp.include_router(start.router)
        
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
