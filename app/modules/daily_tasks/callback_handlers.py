"""
Обработчики callback кнопок для ежедневных задач
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, update

from .filters import IsAdminFilter
from ...database.database import get_async_session
from ...database.models import UserSession
from ...utils.logger import bot_logger
from ...utils.markdown import escape_markdown_v2
from ...config import settings


router = Router()


def is_admin(user_id: int) -> bool:
    """Проверка является ли пользователь админом"""
    return user_id in settings.admin_user_id_list


@router.callback_query(F.data == "setup_email")
async def callback_setup_email(callback: CallbackQuery):
    """Настройка email для уведомлений"""
    admin_id = callback.from_user.id
    
    if not is_admin(admin_id):
        await callback.answer("❌ У вас нет прав для этого действия", show_alert=True)
        return
    
    # Устанавливаем состояние ожидания email
    async for session in get_async_session():
        result = await session.execute(
            select(UserSession).where(UserSession.telegram_user_id == admin_id)
        )
        user_session = result.scalar_one_or_none()
        
        if not user_session:
            user_session = UserSession(
                telegram_user_id=admin_id,
                last_command="setup_email",
                context={"step": "waiting_email"}
            )
            session.add(user_session)
        else:
            user_session.last_command = "setup_email"
            user_session.context = {"step": "waiting_email"}
        
        await session.commit()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_settings")]
    ])
    
    await callback.message.edit_text(
        "📧 *Введите ваш email адрес*\n\n"
        "Этот email будет использоваться для получения задач из Plane\n\n"
        "*Пример:* user@company\\.com",
        reply_markup=keyboard,
        parse_mode="MarkdownV2"
    )
    
    await callback.answer()


@router.callback_query(F.data == "back_to_settings")
async def callback_back_to_settings(callback: CallbackQuery):
    """Возврат к настройкам"""
    admin_id = callback.from_user.id
    
    if not is_admin(admin_id):
        await callback.answer("❌ У вас нет прав для этого действия", show_alert=True)
        return
    
    # Очищаем состояние
    async for session in get_async_session():
        result = await session.execute(
            select(UserSession).where(UserSession.telegram_user_id == admin_id)
        )
        user_session = result.scalar_one_or_none()
        
        if user_session:
            user_session.last_command = None
            user_session.context = {}
            await session.commit()
    
    # Получаем текущие настройки и показываем меню
    from ...services.daily_tasks_service import daily_tasks_service
    
    current_email = "❌ не настроен"
    current_time = "❌ не настроено"
    notifications_enabled = False
    
    if daily_tasks_service:
        bot_logger.info(f"📋 Загружаем настройки для admin {admin_id}")
        admin_settings = daily_tasks_service.admin_settings.get(admin_id, {})
        bot_logger.info(f"📊 Настройки admin {admin_id}: {admin_settings}")
        
        current_email = admin_settings.get('plane_email', '❌ не настроен')
        current_time = admin_settings.get('notification_time', '❌ не настроено')
        notifications_enabled = admin_settings.get('notifications_enabled', False) or admin_settings.get('enabled', False)
        
        bot_logger.info(f"🔧 Итоговые значения: email={current_email}, time={current_time}, enabled={notifications_enabled}")
    else:
        bot_logger.error(f"❌ daily_tasks_service = None при показе настроек admin {admin_id}")
    
    # Экранируем текст для MarkdownV2
    current_email_escaped = escape_markdown_v2(current_email)
    current_time_escaped = escape_markdown_v2(str(current_time))
    status_icon = "🟢 включены" if notifications_enabled else "🔴 отключены"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📧 Email адрес", callback_data="setup_email")],
        [InlineKeyboardButton(text="⏰ Время уведомлений", callback_data="setup_time")],
        [InlineKeyboardButton(text="🔔 Вкл/Выкл уведомления", callback_data="toggle_notifications")],
        [InlineKeyboardButton(text="📋 Показать задачи", callback_data="daily_tasks")],
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
    
    await callback.answer()


@router.callback_query(F.data == "settings_done")
async def callback_settings_done(callback: CallbackQuery):
    """Завершение настройки"""
    await callback.message.edit_text(
        f"✅ *Настройки сохранены*\n\n"
        f"🤖 *Бот настроен и готов к работе*\n"
        f"📧 *Email для задач сохранен*\n"
        f"⏰ *Время уведомлений настроено*\n\n"
        f"Используйте /daily\\_tasks для просмотра задач",
        parse_mode="MarkdownV2"
    )
    await callback.answer()


@router.callback_query(F.data == "daily_tasks")
async def callback_daily_tasks_redirect(callback: CallbackQuery):
    """Redirect для кнопки daily_tasks - просто вызываем cmd_daily_tasks напрямую"""
    admin_id = callback.from_user.id

    if not is_admin(admin_id):
        await callback.answer("❌ У вас нет прав для этого действия", show_alert=True)
        return

    # Перенаправляем на обработчик daily_tasks из handlers.py
    from .handlers import cmd_daily_tasks
    from aiogram.types import Message

    # Создаем фейковое сообщение для вызова обработчика
    fake_message = callback.message
    fake_message.from_user = callback.from_user

    await cmd_daily_tasks(fake_message)
    await callback.answer()


@router.callback_query(F.data == "setup_time")
async def callback_setup_time(callback: CallbackQuery):
    """Настройка времени уведомлений"""
    admin_id = callback.from_user.id
    
    if not is_admin(admin_id):
        await callback.answer("❌ У вас нет прав для этого действия", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🕘 09:00", callback_data="time_09:00")],
        [InlineKeyboardButton(text="🕙 10:00", callback_data="time_10:00")],
        [InlineKeyboardButton(text="🕚 11:00", callback_data="time_11:00")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_settings")]
    ])
    
    await callback.message.edit_text(
        "⏰ *Выберите время для ежедневных уведомлений*\n\n"
        "Задачи будут приходить каждый день в указанное время\\.",
        reply_markup=keyboard,
        parse_mode="MarkdownV2"
    )
    
    await callback.answer()


@router.callback_query(F.data.startswith("time_"))
async def callback_set_time(callback: CallbackQuery):
    """Установка времени уведомлений"""
    admin_id = callback.from_user.id
    
    if not is_admin(admin_id):
        await callback.answer("❌ У вас нет прав для этого действия", show_alert=True)
        return
    
    time_str = callback.data.replace("time_", "")
    
    # Сохраняем время в настройках
    from ...services.daily_tasks_service import daily_tasks_service
    
    if daily_tasks_service:
        if admin_id not in daily_tasks_service.admin_settings:
            daily_tasks_service.admin_settings[admin_id] = {}
        
        # КРИТИЧЕСКИЙ ФИКС: Конвертируем строку времени в time объект
        try:
            from datetime import time as time_obj
            hour, minute = map(int, time_str.split(':'))
            time_object = time_obj(hour, minute)
            daily_tasks_service.admin_settings[admin_id]['notification_time'] = time_object
            bot_logger.info(f"⏰ Конвертировали {time_str} в time объект: {time_object}")
        except Exception as e:
            bot_logger.error(f"❌ Ошибка конвертации времени {time_str}: {e}")
            daily_tasks_service.admin_settings[admin_id]['notification_time'] = time_str
        
        await daily_tasks_service._save_admin_settings_to_db()
        
        bot_logger.info(f"✅ Time {time_str} saved for admin {admin_id}")
    
    await callback.answer(f"✅ Время установлено: {time_str}")
    
    # Возвращаемся к настройкам
    await callback_back_to_settings(callback)


@router.callback_query(F.data == "toggle_notifications")
async def callback_toggle_notifications(callback: CallbackQuery):
    """Включение/отключение уведомлений"""
    admin_id = callback.from_user.id
    
    if not is_admin(admin_id):
        await callback.answer("❌ У вас нет прав для этого действия", show_alert=True)
        return
    
    # Переключаем состояние уведомлений
    from ...services.daily_tasks_service import daily_tasks_service
    
    if daily_tasks_service:
        if admin_id not in daily_tasks_service.admin_settings:
            daily_tasks_service.admin_settings[admin_id] = {}
        
        current_state = daily_tasks_service.admin_settings[admin_id].get('notifications_enabled', False)
        new_state = not current_state
        
        daily_tasks_service.admin_settings[admin_id]['notifications_enabled'] = new_state
        await daily_tasks_service._save_admin_settings_to_db()
        
        status = "включены" if new_state else "отключены"
        await callback.answer(f"✅ Уведомления {status}")
        
        bot_logger.info(f"✅ Notifications {status} for admin {admin_id}")
    
    # Возвращаемся к настройкам
    await callback_back_to_settings(callback)


@router.callback_query(F.data == "start_menu")
async def callback_start_menu(callback: CallbackQuery):
    """Возврат в главное меню"""
    # Показываем стартовое сообщение
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👤 Мои задачи", callback_data="my_tasks"),
            InlineKeyboardButton(text="📁 Все проекты", callback_data="all_projects")
        ],
        [
            InlineKeyboardButton(text="📋 Ежедневные задачи", callback_data="daily_tasks"),
            InlineKeyboardButton(text="📝 Журнал работ", callback_data="work_journal")
        ],
        [
            InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings"),
            InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help_menu")
        ]
    ])
    
    await callback.message.edit_text(
        "👋 *Добро пожаловать в HHIVP IT Assistant Bot\\!*\n\n"
        "🤖 *Функции бота:*\n"
        "• 👤 *Мои задачи* \\- назначенные на вас задачи из Plane\n"
        "• 📁 *Все проекты* \\- просмотр всех проектов и задач\n"
        "• 📋 *Ежедневные задачи* \\- настройка уведомлений\n"
        "• 📝 *Журнал работ* \\- ведение записей о выполненной работе\n"
        "• ⚙️ *Настройки* \\- конфигурация бота\n\n"
        "*Выберите нужный раздел:*",
        reply_markup=keyboard,
        parse_mode="MarkdownV2"
    )
    
    await callback.answer()


@router.callback_query(F.data == "daily_tasks")
async def callback_daily_tasks_menu(callback: CallbackQuery):
    """Показать меню ежедневных задач"""
    admin_id = callback.from_user.id
    
    if not is_admin(admin_id):
        await callback.answer("❌ У вас нет прав для этого действия", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👤 Мои задачи", callback_data="my_tasks"),
            InlineKeyboardButton(text="📁 Все проекты", callback_data="all_projects")
        ],
        [
            InlineKeyboardButton(text="⚙️ Настройки задач", callback_data="back_to_settings"),
            InlineKeyboardButton(text="🔧 Тест Plane API", callback_data="plane_test")
        ],
        [
            InlineKeyboardButton(text="🏠 В главное меню", callback_data="start_menu")
        ]
    ])
    
    await callback.message.edit_text(
        "📋 *Ежедневные задачи*\n\n"
        "Управление задачами из Plane\\.so:\n\n"
        "• 👤 *Мои задачи* \\- просмотр назначенных задач\n"
        "• 📁 *Все проекты* \\- навигация по проектам\n"
        "• ⚙️ *Настройки* \\- email и уведомления\n"
        "• 🔧 *Тест API* \\- проверка подключения\n\n"
        "*Выберите действие:*",
        reply_markup=keyboard,
        parse_mode="MarkdownV2"
    )
    
    await callback.answer()


@router.callback_query(F.data == "plane_test")
async def callback_plane_test_menu(callback: CallbackQuery):
    """Тест Plane API из меню"""
    admin_id = callback.from_user.id
    
    if not is_admin(admin_id):
        await callback.answer("❌ У вас нет прав для этого действия", show_alert=True)
        return
    
    loading_msg = await callback.message.edit_text("🔄 Тестирую подключение к Plane API\\.\\.\\.", parse_mode="MarkdownV2")
    
    try:
        from ...integrations.plane import plane_api
        
        # Проверяем конфигурацию
        if not plane_api.configured:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 В главное меню", callback_data="start_menu")]
            ])
            
            await loading_msg.edit_text(
                "❌ *Plane API не настроен*\n\n"
                "Проверьте настройки в \\.env файле:\n"
                "• PLANE\\_API\\_TOKEN\n"
                "• PLANE\\_API\\_URL\n"
                "• PLANE\\_WORKSPACE\\_SLUG",
                reply_markup=keyboard,
                parse_mode="MarkdownV2"
            )
            return
        
        # Тестируем подключение
        test_result = await plane_api.test_connection()
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Ежедневные задачи", callback_data="daily_tasks")],
            [InlineKeyboardButton(text="🏠 В главное меню", callback_data="start_menu")]
        ])
        
        if test_result.get('success'):
            workspace_escaped = escape_markdown_v2(test_result.get('workspace', 'N/A'))
            projects_count = test_result.get('projects_count', 0)
            await loading_msg.edit_text(
                "✅ *Подключение к Plane API успешно\\!*\n\n"
                f"🏢 *Workspace:* {workspace_escaped}\n"
                f"📁 *Проектов:* {projects_count}\n"
                f"📡 *API Version:* v1\n"
                f"🔗 *API работает корректно*",
                reply_markup=keyboard,
                parse_mode="MarkdownV2"
            )
        else:
            error_msg = escape_markdown_v2(test_result.get('error', 'Неизвестная ошибка'))
            await loading_msg.edit_text(
                f"❌ *Ошибка подключения к Plane API*\n\n"
                f"🔥 *Ошибка:* {error_msg}\n\n"
                f"Проверьте:\n"
                f"• Правильность токена API\n"
                f"• Доступность сервера Plane\n"
                f"• Настройки workspace",
                reply_markup=keyboard,
                parse_mode="MarkdownV2"
            )
            
    except Exception as e:
        bot_logger.error(f"Error in plane_test callback: {e}")
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 В главное меню", callback_data="start_menu")]
        ])
        
        await loading_msg.edit_text(
            f"❌ *Критическая ошибка тестирования*\n\n"
            f"Проверьте конфигурацию Plane API",
            reply_markup=keyboard,
            parse_mode="MarkdownV2"
        )
        
    await callback.answer()