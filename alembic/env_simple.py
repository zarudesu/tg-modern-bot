# Простой env.py для миграций без async
from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlalchemy import MetaData, Column, Integer, BigInteger, String, Boolean, Text, DateTime, JSON, Time
from sqlalchemy.sql import func
from alembic import context
import os

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Создаем метаданные вручную для миграций
metadata = MetaData()

# Базовые таблицы пользователей
bot_users_table = Table('bot_users', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('telegram_user_id', BigInteger, unique=True, nullable=False),
    Column('username', String(255), nullable=True),
    Column('first_name', String(255), nullable=True),
    Column('last_name', String(255), nullable=True),
    Column('role', String(50), default="guest", nullable=False),
    Column('is_active', Boolean, default=True, nullable=False),
    Column('language_code', String(10), default="ru", nullable=False),
    Column('created_at', DateTime, default=func.now(), nullable=False),
    Column('last_seen', DateTime, default=func.now(), nullable=False),
    Column('settings', JSON, default=dict, nullable=False)
)

target_metadata = metadata

def get_database_url():
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        # Конвертируем asyncpg URL в обычный postgresql URL для миграций
        return database_url.replace("postgresql+asyncpg://", "postgresql://")
    
    url = config.get_main_option("sqlalchemy.url")
    return url.replace("postgresql+asyncpg://", "postgresql://") if url else None

def run_migrations_offline() -> None:
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section)
    configuration['sqlalchemy.url'] = get_database_url()
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
