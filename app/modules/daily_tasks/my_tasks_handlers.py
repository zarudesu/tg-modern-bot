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


def is_admin(user_id: int) -> bool:
    """Проверка является ли пользователь админом"""
    return user_id in settings.admin_user_id_list


@router.callback_query(F.data == "my_tasks")
async def callback_my_tasks(callback: CallbackQuery):
    """Показать мои назначенные задачи"""
    admin_id = callback.from_user.id

    if not is_admin(admin_id):
        await callback.answer("❌ У вас нет прав для этого действия", show_alert=True)
        return

    await callback.message.edit_text("🔄 Загружаю ваши задачи\\.\\.\\.", parse_mode="MarkdownV2")

    try:
        tasks = await plane_api.get_all_assigned_tasks_by_user_id(admin_id)

        if not tasks:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📧 Настроить Email", callback_data="setup_email")],
                [InlineKeyboardButton(text="🏠 В главное меню", callback_data="start_menu")]
            ])

            await callback.message.edit_text(
                "📭 У вас нет назначенных задач\n\n"
                "💡 Возможные причины:\n"
                "• Email не настроен в профиле\n"
                "• Нет задач назначенных на ваш email\n"
                "• Все задачи уже выполнены",
                reply_markup=keyboard,
                parse_mode="MarkdownV2"
            )
            return

        if len(tasks) > 10:
            await show_my_tasks_grouped(callback, tasks)
        else:
            await show_my_tasks_list(callback, tasks)

    except Exception as e:
        bot_logger.error(f"Error in my_tasks callback: {e}")
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
        tasks = await plane_api.get_all_assigned_tasks_by_user_id(admin_id)

        if not tasks:
            await callback.message.edit_text(
                "📭 У вас нет назначенных задач",
                parse_mode="MarkdownV2"
            )
            return

        await show_my_tasks_list(callback, tasks)

    except Exception as e:
        bot_logger.error(f"Error in my_tasks_list callback: {e}")
        await callback.message.edit_text(
            "❌ Ошибка загрузки списка задач",
            parse_mode="MarkdownV2"
        )

    await callback.answer()
