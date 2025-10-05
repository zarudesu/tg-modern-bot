"""
Обработчики базовых команд бота
"""
from aiogram import Router, F
from aiogram.types import Message, BotCommand, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command, CommandStart
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime

from ...database.database import get_async_session
from ...database.models import BotUser
from ...utils.formatters import format_help_message, format_user_profile, escape_markdown
from ...utils.logger import bot_logger, log_user_action
from ...config import settings

router = Router()


def create_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Создание основной клавиатуры с частыми функциями"""
    keyboard = [
        [
            InlineKeyboardButton(text="📋 Создать запись", callback_data="start_journal"),
            InlineKeyboardButton(text="📊 История работ", callback_data="show_history")
        ],
        [
            InlineKeyboardButton(text="✈️ Мои задачи из Plane", callback_data="daily_tasks"),
            InlineKeyboardButton(text="⚙️ Настройки задач", callback_data="daily_settings")
        ],
        [
            InlineKeyboardButton(text="📈 Отчеты", callback_data="show_reports"),
            InlineKeyboardButton(text="🏢 Компании", callback_data="manage_companies")
        ],
        [
            InlineKeyboardButton(text="🔄 Синхронизация Google Sheets", callback_data="sheets_sync_menu")
        ],
        [
            InlineKeyboardButton(text="❓ Справка", callback_data="show_help"),
            InlineKeyboardButton(text="👤 Профиль", callback_data="show_profile")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def get_or_create_user(session: AsyncSession, message: Message) -> BotUser:
    """Получить или создать пользователя в базе данных"""
    telegram_user_id = message.from_user.id
    
    # Проверяем, что пользователь - администратор
    if not settings.is_admin(telegram_user_id):
        bot_logger.warning(f"Non-admin user {telegram_user_id} tried to register")
        return None
    
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
    
    # Создаем нового пользователя (только админов)
    role = "admin"  # Все пользователи, которые проходят проверку, являются админами
    
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
    
    bot_logger.info(f"New admin user registered: {telegram_user_id} (@{message.from_user.username})")
    
    return new_user


@router.message(CommandStart())
async def start_command(message: Message, **kwargs):
    """Обработчик команды /start"""
    try:
        # Получаем сессию из middleware
        db_session = kwargs.get('db_session')
        if not db_session:
            bot_logger.error("No database session available in start handler")
            await message.answer(
                "❌ Ошибка базы данных\\. Попробуйте позже\\.",
                parse_mode="MarkdownV2"
            )
            return
            
        user = await get_or_create_user(db_session, message)
        
        # Если пользователь не админ, get_or_create_user вернет None
        # но это сообщение никогда не выполнится, так как AuthMiddleware блокирует раньше
        if not user:
            return
        
        log_user_action(user.telegram_user_id, "start")
        
        # Улучшенное приветствие для администратора
        username = escape_markdown(user.first_name or "Администратор")
        
        welcome_text = f"👋 Добро пожаловать, *{username}*\\!\n\n"
        
        welcome_text += (
            "🤖 Я *HHIVP IT Assistant Bot* \\- ваш помощник по управлению IT\\-работами\\.\n\n"
            "🚀 *Основные возможности:*\n"
            "• 📋 Ведение журнала выполненных работ\n"
            "• 📊 Просмотр истории и статистики\n"
            "• 🏢 Управление компаниями и исполнителями\n"
            "• 📈 Генерация отчетов\n"
            "• ✈️ Ежедневные задачи из Plane\n\n"
            "💡 *Выберите действие из меню ниже или используйте команды\\.*"
        )
        
        await message.answer(
            welcome_text, 
            parse_mode="MarkdownV2",
            reply_markup=create_main_menu_keyboard()
        )
            
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


# ===== ОБРАБОТЧИКИ КНОПОК ГЛАВНОГО МЕНЮ =====

@router.callback_query(F.data == "start_journal")
async def callback_start_journal(callback: CallbackQuery):
    """Перенаправление к созданию записи журнала"""
    try:
        await callback.message.edit_text(
            "📋 *Журнал работ*\n\nДля создания записи используйте команду /journal",
            parse_mode="MarkdownV2"
        )
        await callback.answer()
    except Exception as e:
        bot_logger.error(f"Callback start_journal error: {e}")
        await callback.answer("❌ Ошибка при переходе к журналу")


@router.callback_query(F.data == "show_history")
async def callback_show_history(callback: CallbackQuery):
    """Перенаправление к истории работ"""
    try:
        await callback.message.edit_text(
            "📊 *История работ*\n\nДля просмотра истории используйте команду /history",
            parse_mode="MarkdownV2"
        )
        await callback.answer()
    except Exception as e:
        bot_logger.error(f"Callback show_history error: {e}")
        await callback.answer("❌ Ошибка при переходе к истории")


@router.callback_query(F.data == "daily_tasks")
async def callback_daily_tasks(callback: CallbackQuery):
    """Перенаправление к ежедневным задачам (использует модуль daily_tasks)"""
    try:
        admin_id = callback.from_user.id

        # Проверяем права админа
        if admin_id not in settings.admin_user_id_list:
            await callback.answer("❌ У вас нет прав для этого действия", show_alert=True)
            return

        # Вызываем обработчик команды из модуля daily_tasks
        from ..daily_tasks.handlers import cmd_daily_tasks

        # Создаем фейковое сообщение для вызова обработчика
        fake_message = callback.message
        fake_message.from_user = callback.from_user

        await callback.answer()
        await cmd_daily_tasks(fake_message)

    except Exception as e:
        bot_logger.error(f"Callback daily_tasks error: {e}")
        await callback.answer("❌ Ошибка при переходе к задачам")


@router.callback_query(F.data == "daily_settings")
async def callback_daily_settings(callback: CallbackQuery):
    """Перенаправление к настройкам задач"""
    try:
        admin_id = callback.from_user.id
        
        # Проверяем права админа
        if admin_id not in settings.admin_user_id_list:
            await callback.answer("❌ У вас нет прав для этого действия", show_alert=True)
            return
        
        await callback.answer("⚙️ Открываю настройки...")
        
        # Получаем текущие настройки
        from ...services.daily_tasks_service import daily_tasks_service
        
        current_email = "❌ не настроен"
        current_time = "❌ не настроено" 
        notifications_enabled = False
        
        if daily_tasks_service:
            admin_settings = daily_tasks_service.admin_settings.get(admin_id, {})
            current_email = admin_settings.get('plane_email', '❌ не настроен')
            current_time = admin_settings.get('notification_time', '❌ не настроено')
            notifications_enabled = admin_settings.get('notifications_enabled', False)
        
        # Экранируем специальные символы для MarkdownV2
        current_email_escaped = current_email.replace('_', '\\_').replace('*', '\\*')
        current_time_escaped = str(current_time).replace('_', '\\_').replace('*', '\\*')
        
        status_icon = "🟢 включены" if notifications_enabled else "🔴 отключены"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📧 Email адрес", callback_data="setup_email")],
            [InlineKeyboardButton(text="⏰ Время уведомлений", callback_data="setup_time")],
            [InlineKeyboardButton(text="🔔 Вкл/Выкл уведомления", callback_data="toggle_notifications")],
            [InlineKeyboardButton(text="📋 Показать задачи", callback_data=f"daily_test_{admin_id}")],
            [InlineKeyboardButton(text="✅ Готово", callback_data="settings_done")]
        ])
        
        await callback.message.edit_text(
            f"⚙️ *Настройки ежедневных задач*\n\n"
            f"📧 *Email:* {current_email_escaped}\n"
            f"⏰ *Время:* {current_time_escaped}\n"
            f"🔔 *Уведомления:* {status_icon}\n\n"
            f"Выберите параметр для настройки:",
            reply_markup=keyboard,
            parse_mode="MarkdownV2"
        )
        
    except Exception as e:
        bot_logger.error(f"Callback daily_settings error: {e}")
        await callback.answer("❌ Ошибка при переходе к настройкам")


@router.callback_query(F.data == "show_reports")
async def callback_show_reports(callback: CallbackQuery):
    """Перенаправление к отчетам"""
    try:
        await callback.message.edit_text(
            "📈 *Отчеты*\n\nДля создания отчетов используйте команду /report",
            parse_mode="MarkdownV2"
        )
        await callback.answer()
    except Exception as e:
        bot_logger.error(f"Callback show_reports error: {e}")
        await callback.answer("❌ Ошибка при переходе к отчетам")


@router.callback_query(F.data == "manage_companies")
async def callback_manage_companies(callback: CallbackQuery):
    """Перенаправление к управлению компаниями"""
    try:
        await callback.message.edit_text(
            "🏢 *Управление компаниями*\n\nДля управления компаниями используйте команду /companies",
            parse_mode="MarkdownV2"
        )
        await callback.answer()
    except Exception as e:
        bot_logger.error(f"Callback manage_companies error: {e}")
        await callback.answer("❌ Ошибка при переходе к компаниям")


@router.callback_query(F.data == "sheets_sync_menu")
async def callback_sheets_sync(callback: CallbackQuery):
    """Синхронизация с Google Sheets (временно недоступно)"""
    try:
        await callback.message.edit_text(
            "🔄 *Синхронизация Google Sheets*\n\n❗ Функция временно недоступна после рефакторинга\\.\n\nПланируется восстановление в следующих версиях\\.",
            parse_mode="MarkdownV2"
        )
        await callback.answer()
    except Exception as e:
        bot_logger.error(f"Callback sheets_sync error: {e}")
        await callback.answer("❌ Ошибка при переходе к синхронизации")


@router.callback_query(F.data == "show_help")
async def callback_show_help(callback: CallbackQuery):
    """Показать справку"""
    try:
        help_text = format_help_message()
        await callback.message.edit_text(help_text, parse_mode="MarkdownV2")
        await callback.answer()
    except Exception as e:
        bot_logger.error(f"Callback show_help error: {e}")
        await callback.answer("❌ Ошибка при показе справки")


@router.callback_query(F.data == "show_profile")
async def callback_show_profile(callback: CallbackQuery):
    """Показать профиль пользователя"""
    try:
        user_id = callback.from_user.id
        
        async for session in get_async_session():
            result = await session.execute(
                select(BotUser).where(BotUser.telegram_user_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                await callback.message.edit_text(
                    "❌ Пользователь не найден\\. Используйте /start для регистрации\\.",
                    parse_mode="MarkdownV2"
                )
                await callback.answer()
                return
            
            # Преобразуем в словарь для форматтера
            user_dict = {
                "username": user.username,
                "first_name": user.first_name,
                "role": user.role,
                "created_at": user.created_at,
                "last_seen": user.last_seen
            }
            
            profile_text = format_user_profile(user_dict)
            await callback.message.edit_text(profile_text, parse_mode="MarkdownV2")
            await callback.answer()
            
    except Exception as e:
        bot_logger.error(f"Callback show_profile error: {e}")
        await callback.answer("❌ Ошибка при показе профиля")


# Команды для меню бота
COMMANDS_MENU = [
    BotCommand(command="start", description="🚀 Начать работу с ботом"),
    BotCommand(command="help", description="❓ Справка по командам"),
    BotCommand(command="profile", description="👤 Мой профиль"),
    BotCommand(command="ping", description="🏓 Проверка работоспособности"),
    BotCommand(command="journal", description="📋 Создать запись в журнале работ"),
    BotCommand(command="history", description="📊 История работ"),
    BotCommand(command="report", description="📈 Отчеты по работам"),
    BotCommand(command="companies", description="🏢 Управление компаниями"),
    BotCommand(command="daily_tasks", description="✈️ Мои задачи из Plane"),
    BotCommand(command="daily_settings", description="⚙️ Настройки ежедневных уведомлений"),
    BotCommand(command="plane_test", description="🧪 Тест подключения к Plane"),
]
