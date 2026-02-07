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
from .middleware.rate_limit import RateLimitMiddleware

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

        # Инициализация Redis
        from .services.redis_service import redis_service
        await redis_service.connect(settings.redis_url)
        bot_logger.info(f"✅ Redis initialized (connected={redis_service.is_connected})")

        # Запуск webhook server для n8n
        from .webhooks.server import WebhookServer
        global webhook_server
        webhook_server = WebhookServer(bot)
        webhook_port = getattr(settings, 'webhook_port', 8080)
        await webhook_server.start_server(host='0.0.0.0', port=webhook_port)
        bot_logger.info(f"✅ Webhook server started on port {webhook_port}")

        # 🔥 НОВОЕ: Инициализация AI Manager
        # Приоритет: OpenRouter (работает из РФ) > Groq > OpenAI > Anthropic
        groq_key = getattr(settings, 'groq_api_key', None)
        openrouter_key = getattr(settings, 'openrouter_api_key', None)
        openai_key = getattr(settings, 'openai_api_key', None)
        anthropic_key = getattr(settings, 'anthropic_api_key', None)

        ai_initialized = False

        # 1. Groq — быстрый и умный (llama-3.3-70b), primary для /plane
        if groq_key:
            ai_manager.create_groq_provider(
                api_key=groq_key,
                model="llama-3.3-70b-versatile",
                name="groq",
                set_as_default=False,
                temperature=0.7,
                max_tokens=2000
            )
            bot_logger.info("✅ Groq provider registered (llama-3.3-70b)")
            ai_initialized = True

        # 2. OpenRouter — fallback, бесплатные модели, работает из РФ
        if openrouter_key:
            ai_manager.create_openrouter_provider(
                api_key=openrouter_key,
                model="arcee-ai/trinity-large-preview:free",
                name="openrouter",
                set_as_default=True,
                temperature=0.7,
                max_tokens=1500,
                site_name="HHIVP IT Bot"
            )
            bot_logger.info("✅ OpenRouter provider registered (default)")
            ai_initialized = True

        # 3. Fallback на OpenAI
        elif openai_key:
            ai_manager.create_openai_provider(
                api_key=openai_key,
                model="gpt-4-turbo",
                set_as_default=True,
                temperature=0.7,
                max_tokens=2000
            )
            bot_logger.info("✅ AI Manager initialized with OpenAI")
            ai_initialized = True

        # 4. Fallback на Anthropic
        elif anthropic_key:
            ai_manager.create_anthropic_provider(
                api_key=anthropic_key,
                model="claude-3-haiku-20240307",  # Быстрая и дешёвая
                set_as_default=True,
                temperature=0.7,
                max_tokens=2000
            )
            bot_logger.info("✅ AI Manager initialized with Anthropic")
            ai_initialized = True

        # Инициализация Smart Task Detection (если AI доступен)
        if ai_initialized:
            from .modules.ai_assistant.task_suggestion_handler import init_task_suggestion_handler
            await init_task_suggestion_handler(bot)
            bot_logger.info("✅ Smart Task Detection initialized")
        else:
            bot_logger.warning("⚠️ AI features disabled: No API key found (OpenRouter/OpenAI/Anthropic)")
        
        # Инициализация сервиса ежедневных задач
        from .services.daily_tasks_service import DailyTasksService
        from .services.scheduler import DailyTasksScheduler
        
        # Инициализируем глобальный сервис для использования в модулях
        import app.services.daily_tasks_service as dts_module
        dts_module.daily_tasks_service = DailyTasksService(bot)
        # Загружаем настройки админов из БД
        await dts_module.daily_tasks_service._load_admin_settings_from_db()
        bot_logger.info("Daily tasks service initialized and settings loaded from DB")

        # CACHE DISABLED: Direct API calls instead (rate limit 600/min)
        # User tasks cache service removed - using direct Plane API calls

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
        
        # Morning digest loop (AI-powered daily summary at 09:00 MSK)
        from .integrations.plane import plane_api
        if ai_initialized and plane_api.configured:
            from .modules.plane_assistant.daily_digest import digest_loop
            asyncio.create_task(digest_loop(bot))
            bot_logger.info("✅ Plane morning digest loop started")

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
            "🟢 *HHIVP IT ASSISTANT \\- ЗАПУЩЕН\\!*\n\n"
            f"🤖 @{escaped_username} \\| ID: {bot_info.id}\n"
            f"🕐 {escaped_time}\n"
            f"🧠 AI: {ai_providers_count} провайдеров\n\n"

            f"🤖 *Plane AI* `/plane`\n"
            f"  Задачи, закрытие, назначение, голос\n"
            f"  Groq \\+ OpenRouter \\(fallback\\)\n\n"

            f"☀️ *Утренний дайджест* 09:00 MSK\n"
            f"  TOP\\-3 приоритета, просроченные\n\n"

            f"📨 *Plane → Telegram уведомления*\n"
            f"  Комменты, новые задачи, обновления\n\n"

            f"📋 *Журнал* \\| 📝 *Заявки* \\| 🔧 `/diag`\n\n"

            f"✅ Все системы готовы"
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
        
        # Закрываем Redis
        from .services.redis_service import redis_service
        await redis_service.close()

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

        # 3. Rate limiting (reject spam early, before auth)
        dp.message.middleware(RateLimitMiddleware())
        dp.callback_query.middleware(RateLimitMiddleware())

        # 4. Logging (использует db_session)
        dp.message.middleware(LoggingMiddleware())
        dp.callback_query.middleware(LoggingMiddleware())

        # 5. Group monitoring
        dp.message.middleware(GroupMonitoringMiddleware())

        # 6. Auth (использует db_session)
        dp.message.middleware(AuthMiddleware())
        dp.callback_query.middleware(AuthMiddleware())

        # 7. Event Publisher - публикация событий для Event Bus
        dp.message.middleware(EventPublisherMiddleware())
        dp.callback_query.middleware(EventPublisherMiddleware())

        # Регистрация роутеров в КРИТИЧЕСКИ ВАЖНОМ порядке:
        
        # 1. ОБЩИЕ КОМАНДЫ - базовая функциональность
        dp.include_router(start.router)
        bot_logger.info("✅ Common module loaded (start, help, profile)")

        # 1.5 ADMIN MAPPINGS - управление маппингами через команды
        from .handlers import admin_mappings
        dp.include_router(admin_mappings.router)
        bot_logger.info("✅ Admin Mappings module loaded")

        # 2. DAILY TASKS - НОВЫЕ МОДУЛИ с приоритетным email фильтром
        from .modules.daily_tasks.router import router as daily_tasks_router
        dp.include_router(daily_tasks_router)
        bot_logger.info("✅ Daily Tasks module loaded (NEW modular version with email priority)")

        # 3. Task Reports module - BEFORE voice_transcription for FSM voice handling
        # Voice handler in task_reports uses StateFilter(filling_report) and must be matched first
        from .modules.task_reports.router import router as task_reports_router
        dp.include_router(task_reports_router)
        bot_logger.info("✅ Task Reports module loaded (FSM-based report workflow + voice fill)")

        # 3.5 VOICE TRANSCRIPTION - Whisper API (AFTER task_reports for proper FSM priority)
        from .handlers import voice_transcription
        dp.include_router(voice_transcription.router)
        bot_logger.info("✅ Voice Transcription module loaded")

        # 3.6 AI CALLBACKS - обработка кнопок AI детекции задач и голосовых отчётов
        from .handlers import ai_callbacks
        dp.include_router(ai_callbacks.router)
        bot_logger.info("✅ AI Callbacks module loaded")

        # 4. WORK JOURNAL - state-based work entries
        from .modules.work_journal.router import router as work_journal_router
        dp.include_router(work_journal_router)
        bot_logger.info("✅ Work Journal module loaded (state-based entries)")

        # 5. Google Sheets Sync
        from .handlers import google_sheets_sync
        dp.include_router(google_sheets_sync.router)
        bot_logger.info("✅ Google Sheets Sync module loaded")

        # 6. AI Assistant module - enterprise AI features
        from .modules.ai_assistant.router import router as ai_assistant_router
        dp.include_router(ai_assistant_router)
        bot_logger.info("✅ AI Assistant module loaded")

        # 7. Plane Analysis - /plane_status command
        from .handlers.plane_analysis import router as plane_analysis_router
        dp.include_router(plane_analysis_router)
        bot_logger.info("✅ Plane Analysis module loaded")

        # 7.5. Plane Audit - /plane_audit command
        from .handlers.plane_audit import router as plane_audit_router
        dp.include_router(plane_audit_router)
        bot_logger.info("✅ Plane Audit module loaded")

        # 7.6. Plane Assistant - /plane command (natural language AI)
        from .modules.plane_assistant.router import router as plane_assistant_router
        dp.include_router(plane_assistant_router)
        bot_logger.info("✅ Plane Assistant module loaded")

        # 7.7. AI Training Export - /ai_export command
        from .handlers.ai_training_export import router as ai_export_router
        dp.include_router(ai_export_router)
        bot_logger.info("✅ AI Training Export module loaded")

        # 7.8. System Diagnostics - /diag command
        from .handlers.diagnostics import router as diag_router
        dp.include_router(diag_router)
        bot_logger.info("✅ Diagnostics module loaded")

        # 7.9. AI Quality Analytics - /ai_quality command
        from .handlers.ai_quality import router as ai_quality_router
        dp.include_router(ai_quality_router)
        bot_logger.info("✅ AI Quality module loaded")

        # 8. Chat Support module - /request and /task commands
        from .modules.chat_support.router import router as chat_support_router
        dp.include_router(chat_support_router)
        bot_logger.info("✅ Chat Support module loaded")

        # 8. Chat Monitor module - catches all remaining group messages (LAST)
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
