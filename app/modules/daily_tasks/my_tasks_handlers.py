"""
Обработчики "Мои задачи" - персональные назначенные задачи
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Any

from .filters import IsAdminFilter
from ...integrations.plane import plane_api
from ...utils.logger import bot_logger
from ...utils.markdown import escape_markdown_v2
from ...config import settings


router = Router()

# Global cache for pagination (admin_id -> tasks list)
_my_tasks_cache = {}
MY_TASKS_PER_PAGE = 15


def is_admin(user_id: int) -> bool:
    """Проверка является ли пользователь админом"""
    return user_id in settings.admin_user_id_list


async def _show_my_tasks_page(callback: CallbackQuery, tasks: list, admin_id: int, admin_email: str, page: int = 1):
    """Show my tasks with pagination"""
    from aiogram.types import LinkPreviewOptions

    # Cache tasks for pagination
    _my_tasks_cache[admin_id] = tasks

    total_tasks = len(tasks)
    total_pages = (total_tasks + MY_TASKS_PER_PAGE - 1) // MY_TASKS_PER_PAGE

    # Validate page number
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages

    # Calculate slice
    start_idx = (page - 1) * MY_TASKS_PER_PAGE
    end_idx = start_idx + MY_TASKS_PER_PAGE
    page_tasks = tasks[start_idx:end_idx]

    # Format message
    admin_email_escaped = escape_markdown_v2(admin_email)

    tasks_text = f"👤 *Мои назначенные задачи* \\\\(страница {page}/{total_pages}\\\\)\\n\\n"
    tasks_text += f"📧 *Email:* {admin_email_escaped}\\n"
    tasks_text += f"📊 *Всего задач:* {total_tasks}\\n"
    tasks_text += f"📄 *На странице:* {len(page_tasks)}\\n\\n"

    task_counter = start_idx + 1
    for task in page_tasks:
        task_name_escaped = escape_markdown_v2(task.name)
        project_escaped = escape_markdown_v2(task.project_name)
        status_escaped = escape_markdown_v2(task.state_name or 'Неизвестно')
        task_url = task.task_url

        tasks_text += f"  {task_counter}\\\\. {task.state_emoji} {task.priority_emoji} [{task_name_escaped}]({task_url})\\n"
        tasks_text += f"     📁 {project_escaped} \\\\| 🏷️ {status_escaped}\\n"

        if task.target_date:
            date_escaped = escape_markdown_v2(task.target_date[:10])
            tasks_text += f"     📅 {date_escaped}"
            if task.is_overdue:
                tasks_text += " ⚠️ ПРОСРОЧЕНО"
            elif task.is_due_today:
                tasks_text += " 🔥 СЕГОДНЯ"
            tasks_text += "\\n"

        tasks_text += "\\n"
        task_counter += 1

    # Build pagination keyboard
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"my_tasks_page:{page-1}"
        ))

    nav_buttons.append(InlineKeyboardButton(
        text=f"📄 {page}/{total_pages}",
        callback_data="noop"
    ))

    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton(
            text="Вперёд ➡️",
            callback_data=f"my_tasks_page:{page+1}"
        ))

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        nav_buttons,
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="back_to_settings"),
         InlineKeyboardButton(text="🔄 Обновить", callback_data="my_tasks")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="start_menu")]
    ])

    await callback.message.edit_text(
        tasks_text,
        reply_markup=keyboard,
        parse_mode="MarkdownV2",
        link_preview_options=LinkPreviewOptions(is_disabled=True)
    )


@router.callback_query(F.data == "my_tasks")
async def callback_my_tasks(callback: CallbackQuery):
    """Показать мои назначенные задачи"""
    admin_id = callback.from_user.id

    if not is_admin(admin_id):
        await callback.answer("❌ У вас нет прав для этого действия", show_alert=True)
        return

    await callback.message.edit_text("🔄 Загружаю ваши задачи\\.\\.\\.", parse_mode="MarkdownV2")

    try:
        # Get admin email from settings
        from ...services.daily_tasks_service import daily_tasks_service

        if not daily_tasks_service:
            await callback.message.edit_text(
                "❌ Сервис задач не инициализирован",
                parse_mode="MarkdownV2"
            )
            await callback.answer()
            return

        # Load settings from DB
        await daily_tasks_service._load_admin_settings_from_db()
        admin_settings = daily_tasks_service.admin_settings.get(admin_id, {})
        admin_email = admin_settings.get('plane_email')

        if not admin_email:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📧 Настроить Email", callback_data="setup_email")],
                [InlineKeyboardButton(text="🏠 В главное меню", callback_data="start_menu")]
            ])

            await callback.message.edit_text(
                "📧 *Email не настроен*\n\n"
                "Для получения задач из Plane нужно настроить ваш email\\.",
                reply_markup=keyboard,
                parse_mode="MarkdownV2"
            )
            await callback.answer()
            return

        # Get tasks by email
        bot_logger.info(f"🔄 Fetching tasks for user {admin_id} with email {admin_email}")
        tasks = await plane_api.get_user_tasks(admin_email)
        bot_logger.info(f"✅ Retrieved {len(tasks)} tasks for {admin_email}")

        if not tasks:
            admin_email_escaped = escape_markdown_v2(admin_email)
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить", callback_data="my_tasks")],
                [InlineKeyboardButton(text="🏠 В главное меню", callback_data="start_menu")]
            ])

            await callback.message.edit_text(
                f"📭 *У вас нет назначенных задач*\n\n"
                f"👤 Email: {admin_email_escaped}\n\n"
                f"💡 Возможные причины:\n"
                f"• Нет задач назначенных на ваш email\n"
                f"• Все задачи уже выполнены",
                reply_markup=keyboard,
                parse_mode="MarkdownV2"
            )
            await callback.answer()
            return

        # Show tasks with pagination
        await _show_my_tasks_page(callback, tasks, admin_id, admin_email, page=1)

    except Exception as e:
        bot_logger.error(f"Error in my_tasks callback: {e}", exc_info=True)
        await callback.message.edit_text(
            "❌ Ошибка загрузки ваших задач",
            parse_mode="MarkdownV2"
        )

    await callback.answer()


async def show_my_tasks_grouped(callback: CallbackQuery, tasks: List[Any]):
    """Показать мои задачи сгруппированные по проектам"""
    projects_tasks = {}
    for task in tasks:
        project_name = task.project_name
        if project_name not in projects_tasks:
            projects_tasks[project_name] = []
        projects_tasks[project_name].append(task)

    keyboard_buttons = []

    for project_name, project_tasks in projects_tasks.items():
        display_name = project_name[:35] + "..." if len(project_name) > 35 else project_name

        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"📁 {display_name} ({len(project_tasks)})",
                callback_data=f"my_project_{hash(project_name) % 10000}"
            )
        ])

    keyboard_buttons.extend([
        [InlineKeyboardButton(text="📋 Все мои задачи списком", callback_data="my_tasks_list")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="start_menu")]
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await callback.message.edit_text(
        f"👤 *Мои назначенные задачи*\n\n"
        f"📊 Всего задач: {len(tasks)}\n"
        f"📁 Проектов: {len(projects_tasks)}\n\n"
        f"Задачи сгруппированы по проектам:",
        reply_markup=keyboard,
        parse_mode="MarkdownV2"
    )


async def show_my_tasks_list(callback: CallbackQuery, tasks: List[Any]):
    """Показать список моих задач"""
    keyboard_buttons = []

    for i, task in enumerate(tasks[:10], 1):
        task_title = task.name[:35] + "..." if len(task.name) > 35 else task.name

        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{task.state_emoji} {task.priority_emoji} {task_title}",
                callback_data=f"my_task_{task.project_detail.get('id', 'unknown')}_{task.id}"
            )
        ])

    keyboard_buttons.extend([
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="start_menu")]
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    tasks_text = f"👤 *Мои назначенные задачи*\n\n"

    for i, task in enumerate(tasks[:10], 1):
        task_name_escaped = escape_markdown_v2(task.name)
        project_escaped = escape_markdown_v2(task.project_name)

        tasks_text += f"{i}\\. {task.state_emoji} {task.priority_emoji} {task_name_escaped}\n"
        tasks_text += f"   📁 {project_escaped} \\| 🏷️ {task.state_name}\n"
        if task.target_date:
            date_escaped = escape_markdown_v2(task.target_date[:10])
            tasks_text += f"   📅 {date_escaped}"
            if task.is_overdue:
                tasks_text += " ⚠️ ПРОСРОЧЕНО"
            elif task.is_due_today:
                tasks_text += " 🔥 СЕГОДНЯ"
            tasks_text += "\n"
        tasks_text += "\n"

    if len(tasks) > 10:
        tasks_text += f"\\.\\.\\. и еще {len(tasks) - 10} задач"

    await callback.message.edit_text(
        tasks_text,
        reply_markup=keyboard,
        parse_mode="MarkdownV2"
    )


@router.callback_query(F.data == "my_tasks_list")
async def callback_my_tasks_list(callback: CallbackQuery):
    """Показать все мои задачи списком"""
    admin_id = callback.from_user.id

    if not is_admin(admin_id):
        await callback.answer("❌ У вас нет прав для этого действия", show_alert=True)
        return

    await callback.message.edit_text("🔄 Загружаю ваши задачи\\.\\.\\.", parse_mode="MarkdownV2")

    try:
        # Get admin email from settings
        from ...services.daily_tasks_service import daily_tasks_service

        if not daily_tasks_service:
            await callback.message.edit_text(
                "❌ Сервис задач не инициализирован",
                parse_mode="MarkdownV2"
            )
            await callback.answer()
            return

        # Load settings from DB
        await daily_tasks_service._load_admin_settings_from_db()
        admin_settings = daily_tasks_service.admin_settings.get(admin_id, {})
        admin_email = admin_settings.get('plane_email')

        if not admin_email:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📧 Настроить Email", callback_data="setup_email")],
                [InlineKeyboardButton(text="🏠 В главное меню", callback_data="start_menu")]
            ])

            await callback.message.edit_text(
                "📧 *Email не настроен*\n\n"
                "Для получения задач из Plane нужно настроить ваш email\\.",
                reply_markup=keyboard,
                parse_mode="MarkdownV2"
            )
            await callback.answer()
            return

        # Get tasks by email
        tasks = await plane_api.get_user_tasks(admin_email)

        if not tasks:
            await callback.message.edit_text(
                "📭 У вас нет назначенных задач",
                parse_mode="MarkdownV2"
            )
            await callback.answer()
            return

        # Show tasks with pagination
        await _show_my_tasks_page(callback, tasks, admin_id, admin_email, page=1)

    except Exception as e:
        bot_logger.error(f"Error in my_tasks_list callback: {e}", exc_info=True)
        await callback.message.edit_text(
            "❌ Ошибка загрузки списка задач",
            parse_mode="MarkdownV2"
        )

    await callback.answer()


@router.callback_query(F.data.startswith("my_tasks_page:"))
async def callback_my_tasks_page_navigation(callback: CallbackQuery):
    """Handle pagination navigation for My Tasks"""
    try:
        # Parse callback data: my_tasks_page:page
        parts = callback.data.split(":", 1)
        if len(parts) != 2:
            await callback.answer("❌ Неверный формат данных", show_alert=True)
            return

        page = int(parts[1])
        admin_id = callback.from_user.id

        # Get cached tasks
        if admin_id not in _my_tasks_cache:
            await callback.answer("⚠️ Кэш задач истек, обновите список", show_alert=True)
            return

        tasks = _my_tasks_cache[admin_id]

        # Get admin email from settings
        from ...services.daily_tasks_service import daily_tasks_service
        await daily_tasks_service._load_admin_settings_from_db()
        admin_settings = daily_tasks_service.admin_settings.get(admin_id, {})
        admin_email = admin_settings.get('plane_email', 'unknown')

        # Show requested page
        await _show_my_tasks_page(callback, tasks, admin_id, admin_email, page=page)
        await callback.answer()

    except ValueError as e:
        bot_logger.error(f"Invalid page number in My Tasks pagination: {e}")
        await callback.answer("❌ Неверный номер страницы", show_alert=True)
    except Exception as e:
        bot_logger.error(f"Error in My Tasks pagination callback: {e}")
        await callback.answer("❌ Ошибка навигации", show_alert=True)
