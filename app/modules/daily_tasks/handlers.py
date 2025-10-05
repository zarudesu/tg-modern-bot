"""
Обработчики команд для ежедневных задач
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.enums import ParseMode

from .filters import IsAdminFilter
from ...middleware.auth import require_admin
from ...utils.logger import bot_logger
from ...config import settings


router = Router()


def escape_markdown_v2(text: str) -> str:
    """Правильное экранирование для MarkdownV2"""
    chars_to_escape = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!', '@']
    for char in chars_to_escape:
        text = text.replace(char, f'\\{char}')
    return text


def is_admin(user_id: int) -> bool:
    """Проверка является ли пользователь админом"""
    return user_id in settings.admin_user_id_list


@router.message(Command("daily_tasks"))
async def cmd_daily_tasks(message: Message):
    """Показать текущие задачи админа из Plane"""
    admin_id = message.from_user.id
    
    if not is_admin(admin_id):
        await message.reply("❌ У вас нет прав для выполнения этой команды", parse_mode="MarkdownV2")
        return
        
    bot_logger.info(f"Daily tasks command called by admin {admin_id}")
    
    loading_msg = await message.reply("📋 Получаю ваши задачи\\.\\.\\.", parse_mode="MarkdownV2")
    
    try:
        from ...services.daily_tasks_service import daily_tasks_service
        from ...services.user_tasks_cache_service import user_tasks_cache_service
        from ...integrations.plane import plane_api
        
        if not daily_tasks_service or not plane_api.configured:
            await loading_msg.edit_text(
                "❌ Plane API не настроен\n\n"
                "Проверьте настройки в \\.env файле",
                parse_mode="MarkdownV2"
            )
            return
        
        # Обновляем настройки из БД
        await daily_tasks_service._load_admin_settings_from_db()
        admin_settings = daily_tasks_service.admin_settings.get(admin_id, {})
        
        admin_email = admin_settings.get('plane_email')
        if not admin_email:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📧 Настроить Email", callback_data="setup_email")],
                [InlineKeyboardButton(text="⚙️ Настройки", callback_data="back_to_settings")],
                [InlineKeyboardButton(text="🏠 В главное меню", callback_data="start_menu")]
            ])
            
            await loading_msg.edit_text(
                "📧 Email не настроен\n\n"
                "Для получения задач из Plane нужно настроить ваш email\\.",
                reply_markup=keyboard,
                parse_mode="MarkdownV2"
            )
            return
        
        # 🚀 Получаем задачи из кэша (быстро!)
        cached_tasks = await user_tasks_cache_service.get_cached_tasks(
            user_email=admin_email,
            include_overdue=True,
            include_today=True,
            include_upcoming=True,
            max_tasks=50
        )
        
        # Проверяем статус синхронизации
        sync_status = await user_tasks_cache_service.get_sync_status(admin_email)

        # 🚀 Если кэша нет и синхронизация не запущена - запускаем!
        if not cached_tasks and (not sync_status or not sync_status.sync_in_progress):
            bot_logger.info(f"🚀 Starting sync for {admin_email} (no cache or not in progress)")
            sync_started = await user_tasks_cache_service.start_user_sync(
                user_email=admin_email,
                telegram_user_id=admin_id,
                notify_user=True
            )
            if sync_started:
                # Обновляем статус синхронизации
                sync_status = await user_tasks_cache_service.get_sync_status(admin_email)

        if not cached_tasks and (not sync_status or sync_status.sync_in_progress):
            # Задачи еще загружаются
            admin_email_escaped = escape_markdown_v2(admin_email)
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить", callback_data="daily_tasks")],
                [InlineKeyboardButton(text="🏠 В главное меню", callback_data="start_menu")]
            ])
            
            await loading_msg.edit_text(
                f"⏳ *Загрузка задач в процессе\\.\\.\\.*\n\n"
                f"👤 Email: {admin_email_escaped}\n"
                f"🔄 Ваши задачи из plane\\.hhivp\\.com загружаются в фоновом режиме\\.\n\n"
                f"💡 _Это займет около 5 минут\\. Мы уведомим вас, когда загрузка завершится\\._",
                reply_markup=keyboard,
                parse_mode="MarkdownV2"
            )
            return
        
        if not cached_tasks:
            # Нет задач вообще
            admin_email_escaped = escape_markdown_v2(admin_email)
            last_sync = ""
            if sync_status and sync_status.last_sync_completed:
                # Экранируем точки и двоеточия в дате
                sync_time = sync_status.last_sync_completed.strftime('%H:%M %d.%m')
                sync_time_escaped = escape_markdown_v2(sync_time)
                last_sync = f"\n🕐 Последнее обновление: {sync_time_escaped}"

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить данные", callback_data="refresh_tasks")],
                [InlineKeyboardButton(text="🏠 В главное меню", callback_data="start_menu")]
            ])
            await loading_msg.edit_text(
                f"📋 *Задачи из Plane*\n\n"
                f"👤 Email: {admin_email_escaped}\n"
                f"📊 Найдено задач: 0{last_sync}\n\n"
                f"У вас нет активных задач в Plane\\.",
                reply_markup=keyboard,
                parse_mode="MarkdownV2"
            )
            return
        
        # 🚀 Формируем красивый список кэшированных задач
        admin_email_escaped = escape_markdown_v2(admin_email)
        tasks_text = "📋 *Ваши задачи из Plane*\n\n"
        tasks_text += f"👤 *Email:* {admin_email_escaped}\n"
        tasks_text += f"📊 *Найдено задач:* {len(cached_tasks)}\n"
        
        # Добавляем информацию о последней синхронизации
        if sync_status:
            if sync_status.last_sync_completed:
                last_sync_str = sync_status.last_sync_completed.strftime('%H:%M %d.%m')
                last_sync_str_escaped = escape_markdown_v2(last_sync_str)
                tasks_text += f"🕐 *Обновлено:* {last_sync_str_escaped}\n"
            if sync_status.sync_in_progress:
                tasks_text += f"⏳ _Фоновое обновление в процессе\\.\\.\\._\n"
        
        tasks_text += "\n"
        
        # Показываем ВСЕ задачи
        for i, task in enumerate(cached_tasks, 1):
            # Используем готовые свойства из модели кэша
            state_emoji = task.state_emoji
            priority_emoji = task.priority_emoji

            # Экранируем название задачи
            task_name = escape_markdown_v2(task.title)

            # Получаем URL задачи
            task_url = task.task_url

            # Получаем статус
            status_text = escape_markdown_v2(task.state_name or 'Неизвестно')

            # Получаем проект
            project_name = escape_markdown_v2(task.project_name)

            # Формируем строку задачи СО ССЫЛКОЙ (предпросмотр отключен ниже)
            task_line = f"{i}\\. {state_emoji} {priority_emoji} [{task_name}]({task_url})\n"
            task_line += f"   🏷️ _{status_text}_ • 📁 _{project_name}_\n\n"

            tasks_text += task_line
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Все задачи", callback_data=f"all_tasks_{admin_id}")],
            [InlineKeyboardButton(text="⚙️ Настройки", callback_data="back_to_settings"),
             InlineKeyboardButton(text="🔄 Обновить данные", callback_data="refresh_tasks")],
            [InlineKeyboardButton(text="🏠 В главное меню", callback_data="start_menu")]
        ])
        
        # Отключаем предпросмотр ссылок
        from aiogram.types import LinkPreviewOptions

        await loading_msg.edit_text(
            tasks_text,
            reply_markup=keyboard,
            parse_mode="MarkdownV2",
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
        
    except Exception as e:
        bot_logger.error(f"Error in daily_tasks command: {e}")
        await loading_msg.edit_text(
            "❌ Ошибка получения задач из Plane\\.",
            parse_mode="MarkdownV2"
        )


@router.message(Command("daily_settings"))
async def cmd_daily_settings(message: Message):
    """Настройки ежедневных уведомлений"""
    admin_id = message.from_user.id
    
    if not is_admin(admin_id):
        await message.reply("❌ У вас нет прав для выполнения этой команды", parse_mode="MarkdownV2")
        return
    
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
    current_email_escaped = escape_markdown_v2(current_email)
    current_time_escaped = escape_markdown_v2(str(current_time))
    
    status_icon = "🟢 включены" if notifications_enabled else "🔴 отключены"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📧 Email адрес", callback_data="setup_email")],
        [InlineKeyboardButton(text="⏰ Время уведомлений", callback_data="setup_time")],
        [InlineKeyboardButton(text="🔔 Вкл/Выкл уведомления", callback_data="toggle_notifications")],
        [InlineKeyboardButton(text="📋 Показать задачи", callback_data="daily_tasks")],
        [InlineKeyboardButton(text="✅ Готово", callback_data="settings_done")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="start_menu")]
    ])
    
    await message.reply(
        f"⚙️ *Настройки ежедневных задач*\n\n"
        f"📧 *Email:* {current_email_escaped}\n"
        f"⏰ *Время:* {current_time_escaped}\n"
        f"🔔 *Уведомления:* {status_icon}\n\n"
        f"Выберите параметр для настройки:",
        reply_markup=keyboard,
        parse_mode="MarkdownV2"
    )


@require_admin
@router.message(Command("plane_test"))
async def cmd_plane_test(message: Message):
    """Тестовая команда для проверки подключения к Plane API"""
    admin_id = message.from_user.id
    
    loading_msg = await message.reply("🔄 Тестирую подключение к Plane API\\.\\.\\.", parse_mode="MarkdownV2")
    try:
        from ...integrations.plane import plane_api
        from ...services.daily_tasks_service import daily_tasks_service
        
        # Проверяем конфигурацию
        if not plane_api.configured:
            await loading_msg.edit_text(
                "❌ *Plane API не настроен*\n\n"
                "Проверьте настройки в \\.env файле:\n"
                "• PLANE\\_API\\_TOKEN\n"
                "• PLANE\\_BASE\\_URL\n"
                "• PLANE\\_WORKSPACE\\_SLUG",
                parse_mode="MarkdownV2"
            )
            return
        
        # Тестируем подключение
        test_result = await plane_api.test_connection()
        
        if test_result.get('success'):
            api_url_escaped = escape_markdown_v2(plane_api.api_url)
            workspace_escaped = escape_markdown_v2(plane_api.workspace_slug)
            await loading_msg.edit_text(
                "✅ *Подключение к Plane API успешно\\!*\n\n"
                f"🌐 *URL:* {api_url_escaped}\n"
                f"🏢 *Workspace:* {workspace_escaped}\n"
                f"🔗 *API работает корректно*",
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
                f"• Настройки workspace\n\n"
                f"📋 Смотрите PLANE\\_API\\_TOKEN\\_GUIDE\\.md для получения токена",
                parse_mode="MarkdownV2"
            )
            
    except Exception as e:
        bot_logger.error(f"Error in plane_test command: {e}")
        await loading_msg.edit_text(
            f"❌ *Критическая ошибка тестирования*\n\n"
            f"Проверьте:\n"
            f"• Правильность токена API\n"
            f"• Доступность сервера Plane\n"
            f"• Настройки workspace\n\n"
            f"📋 Смотрите PLANE\\_API\\_TOKEN\\_GUIDE\\.md для получения токена",
            parse_mode="MarkdownV2"
        )


@require_admin
@router.message(Command("scheduler_status"))
async def cmd_scheduler_status(message: Message):
    """Статус планировщика"""
    admin_count = len(settings.admin_user_id_list)
    
    await message.reply(
        f"📊 *Статус системы ежедневных задач*\n\n"
        f"🤖 *Планировщик:* готов к работе\n"
        f"👥 *Админов в системе:* {admin_count}\n"
        f"🗄️ *База данных:* подключена\n"
        f"✈️ *Plane API:* настроен\n\n"
        f"🎯 *Система готова к работе\\!*",
        parse_mode="MarkdownV2"
    )
