"""
Обработчики базовых команд бота
"""
from aiogram import Router, F
from aiogram.types import Message, BotCommand
from aiogram.filters import Command, CommandStart
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime

from ..database.database import get_async_session
from ..database.models import BotUser
from ..utils.formatters import format_help_message, format_user_profile, escape_markdown
from ..utils.logger import bot_logger, log_user_action
from ..config import settings

router = Router()


async def get_or_create_user(session: AsyncSession, message: Message) -> BotUser:
    """Получить или создать пользователя в базе данных"""
    telegram_user_id = message.from_user.id
    
    # Ищем существующего пользователя
    result = await session.execute(
        select(BotUser).where(BotUser.telegram_user_id == telegram_user_id)
    )
    user = result.scalar_one_or_none()
    
    if user:
        # Обновляем время последнего визита
        await session.execute(
            update(BotUser)
            .where(BotUser.telegram_user_id == telegram_user_id)
            .values(last_seen=datetime.utcnow())
        )
        await session.commit()
        return user
    
    # Создаем нового пользователя
    role = "admin" if telegram_user_id == settings.admin_user_id else "guest"
    
    new_user = BotUser(
        telegram_user_id=telegram_user_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        role=role,
        language_code=message.from_user.language_code or "ru"
    )
    
    session.add(new_user)
    await session.commit()
    
    bot_logger.info(f"New user registered: {telegram_user_id} (@{message.from_user.username})")
    
    return new_user


@router.message(CommandStart())
async def start_command(message: Message):
    """Обработчик команды /start"""
    try:
        async for session in get_async_session():
            user = await get_or_create_user(session, message)
            
            log_user_action(user.telegram_user_id, "start")
            
            # Приветствие зависит от роли пользователя
            if user.role == "admin":
                welcome_text = f"👋 Добро пожаловать, *Администратор*\\!\n\n"
            else:
                welcome_text = f"👋 Добро пожаловать, *{escape_markdown(user.first_name or 'Пользователь')}*\\!\n\n"
            
            welcome_text += (
                "🤖 Я *HHIVP IT Management Bot* \\- ваш помощник для управления IT\\-инфраструктурой\\.\n\n"
                "*Мои возможности:*\n"
                "🔍 Поиск устройств в NetBox\n"
                "🏢 Информация о сайтах и стойках\n"
                "🌐 Управление IP адресами\n"
                "🔐 Интеграция с Vaultwarden\n"
                "📚 Поиск в документации Outline\n"
                "🎫 Работа с тикетами Zammad\n\n"
                "Используйте /help для получения списка команд\\."
            )
            
            await message.answer(welcome_text, parse_mode="MarkdownV2")
            
    except Exception as e:
        bot_logger.error(f"Start command error: {e}")
        await message.answer(
            "❌ Произошла ошибка при запуске\\. Попробуйте позже\\.",
            parse_mode="MarkdownV2"
        )


@router.message(Command("help"))
async def help_command(message: Message):
    """Обработчик команды /help"""
    try:
        user_id = message.from_user.id
        log_user_action(user_id, "help")
        
        help_text = format_help_message()
        await message.answer(help_text, parse_mode="MarkdownV2")
        
    except Exception as e:
        bot_logger.error(f"Help command error: {e}")
        await message.answer(
            "❌ Ошибка при получении справки\\.",
            parse_mode="MarkdownV2"
        )


@router.message(Command("profile"))
async def profile_command(message: Message):
    """Обработчик команды /profile"""
    try:
        user_id = message.from_user.id
        
        async for session in get_async_session():
            # Получаем пользователя из базы
            result = await session.execute(
                select(BotUser).where(BotUser.telegram_user_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                await message.answer(
                    "❌ Пользователь не найден\\. Используйте /start для регистрации\\.",
                    parse_mode="MarkdownV2"
                )
                return
            
            log_user_action(user_id, "view_profile")
            
            # Преобразуем в словарь для форматтера
            user_dict = {
                "username": user.username,
                "first_name": user.first_name,
                "role": user.role,
                "created_at": user.created_at,
                "last_seen": user.last_seen
            }
            
            profile_text = format_user_profile(user_dict)
            await message.answer(profile_text, parse_mode="MarkdownV2")
            
    except Exception as e:
        bot_logger.error(f"Profile command error: {e}")
        await message.answer(
            "❌ Ошибка при получении профиля\\.",
            parse_mode="MarkdownV2"
        )


@router.message(Command("ping"))
async def ping_command(message: Message):
    """Обработчик команды /ping для проверки работоспособности"""
    try:
        user_id = message.from_user.id
        log_user_action(user_id, "ping")
        
        await message.answer("🏓 Pong\\! Бот работает нормально\\.", parse_mode="MarkdownV2")
        
    except Exception as e:
        bot_logger.error(f"Ping command error: {e}")
        await message.answer("❌ Ошибка при выполнении ping\\.", parse_mode="MarkdownV2")


# Команды для меню бота
COMMANDS_MENU = [
    BotCommand(command="start", description="🚀 Начать работу с ботом"),
    BotCommand(command="help", description="❓ Справка по командам"),
    BotCommand(command="search", description="🔍 Поиск устройств в NetBox"),
    BotCommand(command="sites", description="🏢 Список сайтов"),
    BotCommand(command="device", description="🖥️ Информация об устройстве"),
    BotCommand(command="profile", description="👤 Мой профиль"),
    BotCommand(command="ping", description="🏓 Проверка работоспособности"),
]
