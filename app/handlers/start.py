"""
Обработчики базовых команд бота
"""
from aiogram import Router, F
from aiogram.types import Message, BotCommand, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
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


def create_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Создание основной клавиатуры с частыми функциями"""
    keyboard = [
        [
            InlineKeyboardButton(text="📋 Создать запись", callback_data="start_journal"),
            InlineKeyboardButton(text="📊 История работ", callback_data="show_history")
        ],
        [
            InlineKeyboardButton(text="✈️ Мои задачи", callback_data="daily_tasks")
        ],
        [
            InlineKeyboardButton(text="⚙️ Настройки", callback_data="show_settings"),
            InlineKeyboardButton(text="❓ Справка", callback_data="show_help")
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
            "• 📈 Генерация отчетов\n\n"
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


# Команды отключены и перенесены в модули
# @router.message(Command("plane_test"))
# async def cmd_plane_test(message: Message):
#     """Перенаправление команды /plane_test в daily_tasks - УДАЛЕНО, теперь в модулях"""


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


@router.callback_query(F.data == "start_menu")
async def callback_main_menu(callback_query: CallbackQuery):
    """Обработчик возврата в главное меню"""
    try:
        user_id = callback_query.from_user.id
        log_user_action(user_id, "main_menu")

        welcome_text = (
            "🏠 *Главное меню*\n\n"
            "Добро пожаловать в HHIVP IT Assistant Bot\\!\n\n"
            "Выберите действие из меню ниже:"
        )

        await callback_query.message.edit_text(
            welcome_text,
            reply_markup=create_main_menu_keyboard(),
            parse_mode="MarkdownV2"
        )
        await callback_query.answer()

    except Exception as e:
        bot_logger.error(f"Main menu callback error: {e}")
        await callback_query.answer("❌ Ошибка при открытии меню", show_alert=True)


@router.callback_query(F.data == "show_settings")
async def callback_settings(callback_query: CallbackQuery):
    """Обработчик меню настроек"""
    try:
        user_id = callback_query.from_user.id

        # Получаем информацию о пользователе
        async for session in get_async_session():
            result = await session.execute(
                select(BotUser).where(BotUser.telegram_user_id == user_id)
            )
            user = result.scalar_one_or_none()

            if not user:
                await callback_query.answer("❌ Пользователь не найден", show_alert=True)
                return

            # Формируем меню настроек
            settings_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✈️ Настройки задач из Plane", callback_data="daily_settings")],
                [InlineKeyboardButton(text="🏢 Компании", callback_data="manage_companies")],
                [InlineKeyboardButton(text="👤 Мой профиль", callback_data="show_profile")],
                [InlineKeyboardButton(text="🏠 В главное меню", callback_data="start_menu")]
            ])

            username = user.username or "Не указан"
            role_emoji = "👑" if user.role == "admin" else "👤"

            settings_text = (
                f"⚙️ *Настройки*\n\n"
                f"{role_emoji} *Пользователь:* @{username}\n"
                f"🎭 *Роль:* {user.role}\n\n"
                f"Выберите раздел настроек:"
            )

            await callback_query.message.edit_text(
                settings_text,
                reply_markup=settings_keyboard,
                parse_mode="MarkdownV2"
            )
            await callback_query.answer()

    except Exception as e:
        bot_logger.error(f"Settings callback error: {e}")
        await callback_query.answer("❌ Ошибка при открытии настроек", show_alert=True)


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


# Команды для меню бота (упрощенное)
COMMANDS_MENU = [
    BotCommand(command="start", description="🏠 Главное меню"),
    BotCommand(command="help", description="❓ Справка"),
    BotCommand(command="daily_tasks", description="✈️ Мои задачи"),
    BotCommand(command="request", description="📝 Создать заявку (в группе)"),
]


# Обработчики callback'ов главного меню
@router.callback_query(F.data == "start_journal")
async def callback_start_journal(callback: CallbackQuery):
    """Обработчик кнопки 'Создать запись'"""
    await callback.answer()
    
    try:
        user_id = callback.from_user.id
        log_user_action(user_id, "start_journal")
        
        async for session in get_async_session():
            from ..services.work_journal_service import WorkJournalService
            from ..utils.work_journal_constants import WorkJournalState, MESSAGE_TEMPLATES, EMOJI
            from ..utils.work_journal_keyboards import create_continue_keyboard
            from ..utils.work_journal_formatters import escape_markdown_v2, format_date_for_display
            from datetime import date
            
            service = WorkJournalService(session)
            
            # Очищаем предыдущее состояние и устанавливаем начальное
            await service.set_user_state(
                user_id,
                WorkJournalState.SELECTING_DATE,
                draft_date=date.today()  # По умолчанию сегодняшняя дата
            )
            
            # Отправляем стартовое сообщение
            start_text = (
                f"{MESSAGE_TEMPLATES['start_entry']}\n\n"
                f"{EMOJI['date']} *Дата:* {escape_markdown_v2(format_date_for_display(date.today()))}"
            )
            
            await callback.message.answer(
                start_text,
                reply_markup=create_continue_keyboard(),
                parse_mode="MarkdownV2"
            )
            
    except Exception as e:
        bot_logger.error(f"Error starting journal entry for user {user_id}: {e}")
        await callback.message.answer(
            "❌ Произошла ошибка\\. Попробуйте позже\\.",
            parse_mode="MarkdownV2"
        )


@router.callback_query(F.data == "show_history")
async def callback_show_history(callback: CallbackQuery):
    """Обработчик кнопки 'История работ'"""
    await callback.answer()
    
    try:
        user_id = callback.from_user.id
        log_user_action(user_id, "view_history")
        
        async for session in get_async_session():
            from ..services.work_journal_service import WorkJournalService
            from ..utils.work_journal_formatters import format_entries_list, format_error_message
            from ..utils.work_journal_keyboards import create_history_menu_keyboard
            from ..utils.work_journal_constants import EMOJI
            
            service = WorkJournalService(session)
            
            # Получаем последние 10 записей пользователя
            entries = await service.get_work_entries(
                telegram_user_id=user_id,
                limit=10
            )
            
            if entries:
                text = format_entries_list(entries, "Последние записи")
            else:
                text = f"*{EMOJI['history']} История работ*\n\nУ вас пока нет записей\\. Создайте первую запись командой /journal\\."
            
            await callback.message.answer(
                text,
                reply_markup=create_history_menu_keyboard(),
                parse_mode="MarkdownV2"
            )
            
    except Exception as e:
        bot_logger.error(f"Error showing work history for user {user_id}: {e}")
        await callback.message.answer(
            "❌ Произошла ошибка\\. Попробуйте позже\\.",
            parse_mode="MarkdownV2"
        )


@router.callback_query(F.data == "show_reports")
async def callback_show_reports(callback: CallbackQuery):
    """Обработчик кнопки 'Отчеты'"""
    await callback.answer()
    
    try:
        user_id = callback.from_user.id
        log_user_action(user_id, "view_reports")
        
        async for session in get_async_session():
            from ..services.work_journal_service import WorkJournalService
            from ..utils.work_journal_formatters import format_statistics_report, format_error_message
            from ..utils.work_journal_keyboards import create_report_menu_keyboard
            from datetime import date, timedelta
            
            service = WorkJournalService(session)
            
            # Получаем статистику за последнюю неделю
            week_ago = date.today() - timedelta(days=7)
            stats = await service.get_statistics(
                telegram_user_id=user_id,
                date_from=week_ago
            )
            
            report_text = format_statistics_report(stats, "Отчет за неделю")
            
            await callback.message.answer(
                report_text,
                reply_markup=create_report_menu_keyboard(),
                parse_mode="MarkdownV2"
            )
            
    except Exception as e:
        bot_logger.error(f"Error showing work reports for user {user_id}: {e}")
        await callback.message.answer(
            "❌ Произошла ошибка\\. Попробуйте позже\\.",
            parse_mode="MarkdownV2"
        )


@router.callback_query(F.data == "manage_companies")
async def callback_manage_companies(callback: CallbackQuery):
    """Обработчик кнопки 'Компании'"""
    await callback.answer()
    
    try:
        user_id = callback.from_user.id
        log_user_action(user_id, "manage_companies")
        
        async for session in get_async_session():
            from ..services.work_journal_service import WorkJournalService
            from ..utils.work_journal_formatters import escape_markdown_v2
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
            service = WorkJournalService(session)
            
            # Получаем список всех компаний
            companies = await service.get_companies()
            
            if not companies:
                await callback.message.answer(
                    "🏢 *Список компаний пуст*\n\nВы можете добавить компании при создании записей в журнале работ\\.",
                    parse_mode="MarkdownV2"
                )
                return
            
            # Формируем текст со списком компаний
            companies_text = "🏢 **Список компаний:**\n\n"
            
            for i, company in enumerate(companies, 1):
                companies_text += f"{i}\\. {escape_markdown_v2(company)}\n"
            
            companies_text += f"\n**Всего компаний:** {len(companies)}\n\n"
            companies_text += "Для удаления используйте:\n"
            companies_text += "`/delete_company Название`"
            
            # Создаем клавиатуру для управления
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="show_main_menu")]
            ])
            
            await callback.message.answer(
                companies_text,
                reply_markup=keyboard,
                parse_mode="MarkdownV2"
            )
            
    except Exception as e:
        bot_logger.error(f"Error managing companies for user {user_id}: {e}")
        await callback.message.answer("❌ Произошла ошибка при получении списка компаний\\.", parse_mode="MarkdownV2")


@router.callback_query(F.data == "show_help")
async def callback_show_help(callback: CallbackQuery):
    """Обработчик кнопки 'Справка'"""
    await callback.answer()
    await callback.message.answer(
        format_help_message(),
        parse_mode="MarkdownV2"
    )


@router.callback_query(F.data == "show_profile")
async def callback_show_profile(callback: CallbackQuery):
    """Обработчик кнопки 'Профиль'"""
    await callback.answer()
    
    try:
        user_id = callback.from_user.id
        
        async for session in get_async_session():
            # Получаем пользователя из базы
            result = await session.execute(
                select(BotUser).where(BotUser.telegram_user_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                await callback.message.answer(
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
            await callback.message.answer(profile_text, parse_mode="MarkdownV2")
            
    except Exception as e:
        bot_logger.error(f"Profile callback error: {e}")
        await callback.message.answer(
            "❌ Ошибка при получении профиля\\.",
            parse_mode="MarkdownV2"
        )


@router.callback_query(F.data == "daily_tasks")
async def callback_daily_tasks(callback: CallbackQuery):
    """Обработчик кнопки 'Мои задачи из Plane'"""
    await callback.answer()
    
    # Проверяем права админа
    user_id = callback.from_user.id
    if not settings.is_admin(user_id):
        await callback.message.answer("❌ У вас нет прав для просмотра задач Plane")
        return
    
    # Перенаправляем на команду daily_tasks
    from ..modules.daily_tasks.handlers import cmd_daily_tasks
    
    # Создаем фиктивное сообщение для обработчика
    fake_message = type('FakeMessage', (), {
        'from_user': callback.from_user,
        'reply': callback.message.answer,
        'answer': callback.message.answer
    })()
    
    await cmd_daily_tasks(fake_message)


@router.callback_query(F.data == "show_main_menu")
async def callback_show_main_menu(callback: CallbackQuery):
    """Обработчик возврата в главное меню"""
    await callback.answer()
    
    try:
        user_id = callback.from_user.id
        
        async for session in get_async_session():
            user = await get_or_create_user(session, type('FakeMessage', (), {
                'from_user': callback.from_user
            })())
            
            if not user:
                return
            
            username = escape_markdown(user.first_name or "Администратор")
            
            welcome_text = f"👋 *{username}*\\!\n\n"
            welcome_text += (
                "🤖 Я *HHIVP IT Assistant Bot* \\- ваш помощник по управлению IT\\-работами\\.\n\n"
                "💡 *Выберите действие из меню ниже или используйте команды\\.*"
            )
            
            await callback.message.edit_text(
                welcome_text, 
                parse_mode="MarkdownV2",
                reply_markup=create_main_menu_keyboard()
            )
            
    except Exception as e:
        bot_logger.error(f"Error showing main menu: {e}")
        await callback.message.answer(
            "❌ Произошла ошибка\\. Попробуйте позже\\.",
            parse_mode="MarkdownV2"
        )


@router.callback_query(F.data == "sheets_sync_menu")
async def callback_sheets_sync_menu(callback: CallbackQuery):
    """Обработчик кнопки 'Синхронизация Google Sheets'"""
    await callback.answer()
    
    try:
        # Перенаправляем на команду из google_sheets_sync
        from ..handlers.google_sheets_sync import cmd_sheets_sync_menu
        
        # Создаем фиктивное сообщение для обработчика
        fake_message = type('FakeMessage', (), {
            'from_user': callback.from_user,
            'reply': callback.message.answer,
            'answer': callback.message.answer
        })()
        
        await cmd_sheets_sync_menu(fake_message)
        
    except Exception as e:
        bot_logger.error(f"Error in sheets sync menu: {e}")
        await callback.message.answer(
            "❌ Произошла ошибка при открытии меню синхронизации\\.",
            parse_mode="MarkdownV2"
        )



@router.callback_query(F.data == "daily_settings")
async def callback_daily_settings(callback: CallbackQuery):
    """Обработчик кнопки 'Настройки задач'"""
    await callback.answer()
    
    # Проверяем права админа
    user_id = callback.from_user.id
    if not settings.is_admin(user_id):
        await callback.message.answer("❌ У вас нет прав для настройки задач Plane")
        return
    
    try:
        # Перенаправляем на команду daily_settings
        from ..modules.daily_tasks.handlers import cmd_daily_settings
        
        # Создаем фиктивное сообщение для обработчика
        fake_message = type('FakeMessage', (), {
            'from_user': callback.from_user,
            'reply': callback.message.answer,
            'answer': callback.message.answer
        })()
        
        await cmd_daily_settings(fake_message)
        
    except Exception as e:
        bot_logger.error(f"Error in daily settings: {e}")
        await callback.message.answer(
            "❌ Произошла ошибка при открытии настроек\\\\.",
            parse_mode="MarkdownV2"
        )
