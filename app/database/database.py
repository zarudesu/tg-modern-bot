"""
Настройка подключения к базе данных
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from .models import Base
from ..config import settings
from ..utils.logger import bot_logger


# Создание асинхронного движка
engine = create_async_engine(
    settings.database_url,
    echo=settings.log_level == "DEBUG",
    poolclass=StaticPool,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# Создание фабрики сессий
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Получение асинхронной сессии базы данных"""
    session = AsyncSessionLocal()
    try:
        yield session
    except Exception as e:
        await session.rollback()
        bot_logger.error(f"Database session error: {e}")
        raise
    finally:
        await session.close()


async def init_db():
    """Инициализация базы данных"""
    try:
        async with engine.begin() as conn:
            # Создание всех таблиц
            await conn.run_sync(Base.metadata.create_all)
        bot_logger.info("Database initialized successfully")
    except Exception as e:
        bot_logger.error(f"Database initialization failed: {e}")
        raise


async def close_db():
    """Закрытие подключения к базе данных"""
    try:
        await engine.dispose()
        bot_logger.info("Database connection closed")
    except Exception as e:
        bot_logger.error(f"Error closing database: {e}")
