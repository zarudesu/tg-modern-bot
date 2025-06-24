import asyncio
import os
from loguru import logger
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.storage.redis import RedisStorage
import redis.asyncio as redis

from config import settings
from handlers import search, admin, help
from database import init_db

async def main():
    """Главная функция запуска бота"""
    
    # Настройка логирования
    logger.add(
        "logs/bot.log",
        rotation="1 day",
        retention="7 days",
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}"
    )
    
    logger.info("🚀 Запуск HHIVP IT-Bot...")
    
    # Инициализация Redis для FSM
    redis_client = redis.from_url(settings.REDIS_URL)
    storage = RedisStorage(redis_client)
    
    # Инициализация бота и диспетчера
    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher(storage=storage)
    
    # Инициализация базы данных
    await init_db()
    
    # Регистрация роутеров
    dp.include_router(help.router)
    dp.include_router(search.router)
    dp.include_router(admin.router)
    
    try:
        # Получение информации о боте
        bot_info = await bot.get_me()
        logger.info(f"🤖 Бот запущен: @{bot_info.username}")
        
        # Запуск polling
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске бота: {e}")
    finally:
        await bot.session.close()
        await redis_client.close()

if __name__ == "__main__":
    # Создаем директорию для логов
    os.makedirs("logs", exist_ok=True)
    
    # Запуск бота
    asyncio.run(main())
