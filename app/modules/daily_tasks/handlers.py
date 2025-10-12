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
from ...utils.markdown import escape_markdown_v2
from ...config import settings


router = Router()

# Global cache for pagination (email -> tasks list)
_tasks_cache = {}
TASKS_PER_PAGE = 15


def is_admin(user_id: int) -> bool:
    """Проверка является ли пользователь админом"""
    return user_id in settings.admin_user_id_list


async def _show_tasks_page(message, tasks: list, admin_email: str, page: int = 1):
    """Show tasks with pagination"""
    from aiogram.types import LinkPreviewOptions

    # Cache tasks for pagination
    _tasks_cache[admin_email] = tasks

    total_tasks = len(tasks)
    total_pages = (total_tasks + TASKS_PER_PAGE - 1) // TASKS_PER_PAGE

    # Validate page number
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages

    # Calculate slice
    start_idx = (page - 1) * TASKS_PER_PAGE
    end_idx = start_idx + TASKS_PER_PAGE
    page_tasks = tasks[start_idx:end_idx]

    # Format message
    admin_email_escaped = escape_markdown_v2(admin_email)

    # Group tasks by project
    tasks_by_project = {}
    for task in page_tasks:
        project_name = task.project_name
        if project_name not in tasks_by_project:
            tasks_by_project[project_name] = []
        tasks_by_project[project_name].append(task)

    tasks_text = f"📋 *Задачи из Plane* \\(страница {page}/{total_pages}\\)\n\n"
    tasks_text += f"👤 *Email:* {admin_email_escaped}\n"
    tasks_text += f"📊 *Всего задач:* {total_tasks}\n"
    tasks_text += f"📄 *На странице:* {len(page_tasks)}\n\n"

    task_counter = start_idx + 1
    for project_name, project_tasks in tasks_by_project.items():
        project_name_escaped = escape_markdown_v2(project_name)
        tasks_text += f"📁 *{project_name_escaped}* \\({len(project_tasks)}\\)\n"

        for task in project_tasks:
            state_emoji = task.state_emoji
            priority_emoji = task.priority_emoji
            task_name = escape_markdown_v2(task.name)
            task_url = task.task_url
            status_text = escape_markdown_v2(task.state_name or 'Неизвестно')

            tasks_text += f"  {task_counter}\\. {state_emoji} {priority_emoji} [{task_name}]({task_url})\n"
            tasks_text += f"     🏷️ {status_text}\n"
            task_counter += 1

        tasks_text += "\n"

    # Build pagination keyboard
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"tasks_page:{admin_email}:{page-1}"
        ))

    nav_buttons.append(InlineKeyboardButton(
        text=f"📄 {page}/{total_pages}",
        callback_data="noop"
    ))

    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton(
            text="Вперёд ➡️",
            callback_data=f"tasks_page:{admin_email}:{page+1}"
        ))

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        nav_buttons,
        [InlineKeyboardButton(text="📁 По проектам", callback_data="all_projects")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="back_to_settings"),
         InlineKeyboardButton(text="🔄 Обновить", callback_data="daily_tasks")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="start_menu")]
    ])

    await message.edit_text(
        tasks_text,
        reply_markup=keyboard,
        parse_mode="MarkdownV2",
        link_preview_options=LinkPreviewOptions(is_disabled=True)
    )


@router.message(Command("daily_tasks"))
async def cmd_daily_tasks(message: Message):
    """Показать текущие задачи админа из Plane (ПРЯМОЙ запрос к API)"""
    admin_id = message.from_user.id

    if not is_admin(admin_id):
        await message.reply("❌ У вас нет прав для выполнения этой команды", parse_mode="MarkdownV2")
        return

    bot_logger.info(f"Daily tasks command called by admin {admin_id}")

    loading_msg = await message.reply("📋 Загружаю ваши задачи из Plane\\.\\.\\.\n⏱️ _Это займет \\~15 секунд_", parse_mode="MarkdownV2")

    try:
        from ...services.daily_tasks_service import daily_tasks_service
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

        # 🚀 ПРЯМОЙ запрос к Plane API (с оптимизированным rate limit 600/min)
        bot_logger.info(f"🔄 Fetching tasks directly from Plane API for {admin_email}")
        tasks = await plane_api.get_user_tasks(admin_email)
        bot_logger.info(f"✅ Retrieved {len(tasks)} tasks from Plane API")

        if not tasks:
            # Нет задач вообще
            admin_email_escaped = escape_markdown_v2(admin_email)
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить", callback_data="daily_tasks")],
                [InlineKeyboardButton(text="🏠 В главное меню", callback_data="start_menu")]
            ])
            await loading_msg.edit_text(
                f"📋 *Задачи из Plane*\n\n"
                f"👤 Email: {admin_email_escaped}\n"
                f"📊 Найдено задач: 0\n\n"
                f"У вас нет активных задач в Plane\\.",
                reply_markup=keyboard,
                parse_mode="MarkdownV2"
            )
            return

        # 🚀 Формируем красивый список задач С ПАГИНАЦИЕЙ
        await _show_tasks_page(loading_msg, tasks, admin_email, page=1)

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


@router.callback_query(F.data.startswith("tasks_page:"))
async def callback_tasks_page_navigation(callback: CallbackQuery):
    """Handle pagination navigation"""
    try:
        # Parse callback data: tasks_page:email:page
        parts = callback.data.split(":", 2)
        if len(parts) != 3:
            await callback.answer("❌ Неверный формат данных", show_alert=True)
            return

        admin_email = parts[1]
        page = int(parts[2])

        # Get cached tasks
        if admin_email not in _tasks_cache:
            await callback.answer("⚠️ Кэш задач истек, обновите список", show_alert=True)
            return

        tasks = _tasks_cache[admin_email]

        # Show requested page
        await _show_tasks_page(callback.message, tasks, admin_email, page=page)
        await callback.answer()

    except ValueError as e:
        bot_logger.error(f"Invalid page number in pagination: {e}")
        await callback.answer("❌ Неверный номер страницы", show_alert=True)
    except Exception as e:
        bot_logger.error(f"Error in pagination callback: {e}")
        await callback.answer("❌ Ошибка навигации", show_alert=True)
