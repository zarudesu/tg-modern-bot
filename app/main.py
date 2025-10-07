"""
Основной файл Telegram бота HHIVP IT Management - ПОЛНАЯ РЕФАКТОРИРОВАННАЯ ВЕРСИЯ
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
from .middleware.event_publisher import EventPublisherMiddleware

# Core системы
from .core.events.event_bus import event_bus
from .core.plugins.plugin_manager import plugin_manager
from .core.ai.ai_manager import ai_manager

# ИСПРАВЛЕННЫЕ ИМПОРТЫ
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
    bot_logger.info("🚀 Bot startup initiated - ENTERPRISE ARCHITECTURE")

    try:
        # Инициализация базы данных
        await init_db()
        bot_logger.info("✅ Database initialized")

        # Запуск webhook server для n8n
        from .webhooks.server import WebhookServer
        global webhook_server
        webhook_server = WebhookServer(bot)
        webhook_port = getattr(settings, 'webhook_port', 8080)
        await webhook_server.start_server(host='0.0.0.0', port=webhook_port)
        bot_logger.info(f"✅ Webhook server started on port {webhook_port}")

        # 🔥 НОВОЕ: Инициализация AI Manager (если есть API ключи)
        ai_api_key = getattr(settings, 'openai_api_key', None)
        if ai_api_key:
            ai_manager.create_openai_provider(
                api_key=ai_api_key,
                model="gpt-4-turbo",
                set_as_default=True,
                temperature=0.7,
                max_tokens=2000
            )
            bot_logger.info("✅ AI Manager initialized with OpenAI")
        else:
            bot_logger.warning("⚠️ AI features disabled: No API key found")
        
        # Инициализация сервиса ежедневных задач
        from .services.daily_tasks_service import DailyTasksService
        from .services.scheduler import DailyTasksScheduler
        
        # Инициализируем глобальный сервис для использования в модулях
        import app.services.daily_tasks_service as dts_module
        dts_module.daily_tasks_service = DailyTasksService(bot)
        # Загружаем настройки админов из БД
        await dts_module.daily_tasks_service._load_admin_settings_from_db()
        bot_logger.info("Daily tasks service initialized and settings loaded from DB")
        
        # Инициализируем кэш сервис задач пользователей
        from .services.user_tasks_cache_service import user_tasks_cache_service
        user_tasks_cache_service.bot_instance = bot
        bot_logger.info("User tasks cache service bot instance set")
        
        # Запуск планировщика ежедневных задач
        global scheduler
        scheduler = None
        try:
            scheduler = DailyTasksScheduler()
            if settings.daily_tasks_enabled:
                await scheduler.start()
                bot_logger.info("Daily tasks scheduler started")
        except Exception as e:
            bot_logger.error(f"Scheduler error: {e}")
            bot_logger.info("Daily tasks scheduler disabled due to error")
        
        # Настройка команд бота
        await setup_bot_commands(bot)
        
        # Получаем информацию о боте
        bot_info = await bot.get_me()
        bot_logger.info(f"Bot started: @{bot_info.username} (ID: {bot_info.id})")
        
        # Уведомляем всех администраторов о запуске
        from datetime import datetime
        escaped_time = datetime.now().strftime("%d\\.%m\\.%Y %H:%M:%S")
        escaped_username = bot_info.username.replace('_', '\\_')
        
        # Подсчёт зарегистрированных компонентов
        event_types_count = len(event_bus.registered_event_types)
        plugins_count = plugin_manager.loaded_plugins_count
        ai_providers_count = ai_manager.providers_count

        startup_message = (
            "🟢 *ENTERPRISE BOT ЗАПУЩЕН\\!*\n\n"
            f"🤖 *Username:* @{escaped_username}\n"
            f"🆔 *Bot ID:* {bot_info.id}\n"
            f"📊 *Версия:* v3\\.0 ENTERPRISE\n"
            f"🕐 *Время запуска:* {escaped_time}\n\n"
            f"🎯 *ENTERPRISE ВОЗМОЖНОСТИ:*\n"
            f"🧠 AI Assistant \\- {ai_providers_count} провайдеров\n"
            f"📡 Event Bus \\- {event_types_count} типов событий\n"
            f"🔌 Plugin System \\- {plugins_count} плагинов\n"
            f"📧 Email изоляция для daily\\_tasks\n"
            f"📋 Work journal с фильтрами\n"
            f"🔧 Модульная архитектура\n"
            f"👀 Chat Monitor \\- чтение групп\n"
            f"🤖 Авто\\-задачи из чатов\n\n"
            f"✅ *Статус:* Все системы готовы к работе"
        )
        
        # Создаём кнопку Старт
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        startup_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Старт", callback_data="start_menu")]
        ])

        for admin_id in settings.admin_user_id_list:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=startup_message,
                    reply_markup=startup_keyboard,
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
        # Уведомляем всех администраторов о завершении
        shutdown_message = (
            "🔴 *HHIVP IT Assistant Bot завершает работу\\.*\n\n"
            "🛑 Все процессы будут остановлены\\."
        )
        
        for admin_id in settings.admin_user_id_list:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=shutdown_message,
                    parse_mode="MarkdownV2"
                )
            except Exception as e:
                bot_logger.warning(f"Could not notify admin {admin_id} about shutdown: {e}")
        
        # Остановка планировщика
        global scheduler
        if scheduler and hasattr(scheduler, 'is_running') and scheduler.is_running():
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
    bot_logger.info("🚀 Starting HHIVP IT Assistant Bot - REFACTORED VERSION")
    
    try:
        # Создание бота и диспетчера с правильными timeout настройками
        from aiohttp import ClientTimeout
        from aiogram.fsm.storage.memory import MemoryStorage

        bot = Bot(
            token=settings.telegram_token,
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2),
            session=None  # Используем сессию по умолчанию с настройками timeout
        )

        # FSM storage с поддержкой групп (user_id + chat_id)
        storage = MemoryStorage()
        dp = Dispatcher(storage=storage)
        
        # Регистрация middleware (порядок важен!)
        # 1. Database Session - должен быть первым и только ОДИН раз
        dp.message.middleware(DatabaseSessionMiddleware())
        dp.callback_query.middleware(DatabaseSessionMiddleware())
        
        # 2. Performance monitoring  
        dp.message.middleware(PerformanceMiddleware())
        dp.callback_query.middleware(PerformanceMiddleware())
        
        # 3. Logging (использует db_session)
        dp.message.middleware(LoggingMiddleware())
        dp.callback_query.middleware(LoggingMiddleware())
        
        # 4. Group monitoring
        dp.message.middleware(GroupMonitoringMiddleware())
        
        # 5. Auth (использует db_session)
        dp.message.middleware(AuthMiddleware())
        dp.callback_query.middleware(AuthMiddleware())

        # 6. Event Publisher - публикация событий для Event Bus
        dp.message.middleware(EventPublisherMiddleware())
        dp.callback_query.middleware(EventPublisherMiddleware())

        # Регистрация роутеров в КРИТИЧЕСКИ ВАЖНОМ порядке:
        
        # 1. ОБЩИЕ КОМАНДЫ - базовая функциональность
        dp.include_router(start.router)
        bot_logger.info("✅ Common module loaded (start, help, profile)")
        
        # 2. DAILY TASKS - НОВЫЕ МОДУЛИ с приоритетным email фильтром
        from .modules.daily_tasks.router import router as daily_tasks_router
        dp.include_router(daily_tasks_router)
        bot_logger.info("✅ Daily Tasks module loaded (NEW modular version with email priority)")
        
        # 3. WORK JOURNAL - НОВЫЕ МОДУЛИ с фильтрами активности
        from .modules.work_journal.router import router as work_journal_router
        dp.include_router(work_journal_router)
        bot_logger.info("✅ Work Journal module loaded (NEW modular version with state filters)")
        
        # 4. Google Sheets Sync
        from .handlers import google_sheets_sync
        dp.include_router(google_sheets_sync.router)
        bot_logger.info("✅ Google Sheets Sync module loaded")

        # 5. AI Assistant module - enterprise AI features
        from .modules.ai_assistant.router import router as ai_assistant_router
        dp.include_router(ai_assistant_router)
        bot_logger.info("✅ AI Assistant module loaded")

        # 6. Chat Support module - simple request handling from groups (ПЕРЕД chat_monitor!)
        from .modules.chat_support.router import router as chat_support_router
        dp.include_router(chat_support_router)
        bot_logger.info("✅ Chat Support module loaded (simple /request flow)")

        # 7. Task Reports module - automated client reporting for completed tasks
        from .modules.task_reports.router import router as task_reports_router
        dp.include_router(task_reports_router)
        bot_logger.info("✅ Task Reports module loaded (FSM-based report workflow)")

        # 8. Chat Monitor module - чтение групповых чатов (ПОСЛЕДНИМ - ловит всё остальное)
        from .modules.chat_monitor.router import router as chat_monitor_router
        dp.include_router(chat_monitor_router)
        bot_logger.info("✅ Chat Monitor module loaded")

        bot_logger.info("🎯 All modules loaded successfully with proper isolation")
        
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


async def health_check():
    """Health check для production мониторинга"""
    try:
        # Проверяем подключение к базе данных
        from .database.database import get_async_session
        async for session in get_async_session():
            await session.execute(text("SELECT 1"))
            break
        
        return True
    except Exception as e:
        bot_logger.error(f"Health check failed: {e}")
        return False
