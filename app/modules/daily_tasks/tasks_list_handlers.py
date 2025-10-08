"""
Обработчики списков задач (все задачи, проекты, задачи проекта)
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from .filters import IsAdminFilter
from ...integrations.plane import plane_api
from ...utils.logger import bot_logger
from ...utils.markdown import escape_markdown_v2
from ...config import settings


router = Router()


def is_admin(user_id: int) -> bool:
    """Проверка является ли пользователь админом"""
    return user_id in settings.admin_user_id_list


@router.callback_query(F.data.startswith("all_tasks_"))
async def callback_all_tasks(callback: CallbackQuery):
    """Показать все задачи админа с группировкой по проектам"""
    admin_id = callback.from_user.id

    if not is_admin(admin_id):
        await callback.answer("❌ У вас нет прав для этого действия", show_alert=True)
        return

    loading_msg = await callback.message.edit_text(
        "📋 Загружаю все задачи из Plane\\.\\.\\.\n⏱️ _Это займет \\~15 секунд_",
        parse_mode="MarkdownV2"
    )

    try:
        from ...services.daily_tasks_service import daily_tasks_service

        if not daily_tasks_service or not plane_api.configured:
            await loading_msg.edit_text(
                "❌ Plane API не настроен",
                parse_mode="MarkdownV2"
            )
            return

        await daily_tasks_service._load_admin_settings_from_db()
        admin_settings = daily_tasks_service.admin_settings.get(admin_id, {})

        admin_email = admin_settings.get('plane_email')
        if not admin_email:
            await loading_msg.edit_text(
                "📧 Email не настроен\n\n"
                "Сначала настройте email для получения задач\\.",
                parse_mode="MarkdownV2"
            )
            return

        bot_logger.info(f"🔄 Fetching ALL tasks from Plane API for {admin_email}")
        tasks = await plane_api.get_user_tasks(admin_email)
        bot_logger.info(f"✅ Retrieved {len(tasks)} tasks from Plane API")

        if not tasks:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"all_tasks_{admin_id}")],
                [InlineKeyboardButton(text="🏠 В главное меню", callback_data="start_menu")]
            ])
            await loading_msg.edit_text(
                f"📋 *Все задачи из Plane*\n\n"
                f"👤 Email: {escape_markdown_v2(admin_email)}\n"
                f"📊 Найдено задач: 0\n\n"
                f"У вас нет активных задач в Plane\\.",
                reply_markup=keyboard,
                parse_mode="MarkdownV2"
            )
            return

        # Группируем задачи по проектам
        tasks_by_project = {}
        for task in tasks:
            project_name = task.project_name
            if project_name not in tasks_by_project:
                tasks_by_project[project_name] = []
            tasks_by_project[project_name].append(task)

        # Формируем красивый вывод
        admin_email_escaped = escape_markdown_v2(admin_email)
        tasks_text = f"📋 *Все задачи из Plane*\n\n"
        tasks_text += f"👤 *Email:* {admin_email_escaped}\n"
        tasks_text += f"📊 *Всего задач:* {len(tasks)}\n"
        tasks_text += f"📁 *Проектов:* {len(tasks_by_project)}\n\n"

        task_counter = 1
        for project_name, project_tasks in tasks_by_project.items():
            project_name_escaped = escape_markdown_v2(project_name)
            tasks_text += f"📁 *{project_name_escaped}* \\({len(project_tasks)} задач\\)\n"

            # Показываем ВСЕ задачи (убран лимит [:5])
            for task in project_tasks:
                state_emoji = task.state_emoji
                priority_emoji = task.priority_emoji
                task_name = escape_markdown_v2(task.name)
                task_url = task.task_url
                status_text = escape_markdown_v2(task.state_name or 'Неизвестно')
                project_escaped = escape_markdown_v2(task.project_name)

                tasks_text += f"  {task_counter}\\. {state_emoji} {priority_emoji} [{task_name}]({task_url})\n"
                tasks_text += f"     📁 {project_escaped} \\| 🏷️ {status_text}\n"
                task_counter += 1

            tasks_text += "\n"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📁 По проектам", callback_data="all_projects")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="daily_tasks"),
             InlineKeyboardButton(text="🔄 Обновить", callback_data=f"all_tasks_{admin_id}")],
            [InlineKeyboardButton(text="🏠 В главное меню", callback_data="start_menu")]
        ])

        from aiogram.types import LinkPreviewOptions

        await loading_msg.edit_text(
            tasks_text,
            reply_markup=keyboard,
            parse_mode="MarkdownV2",
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )

    except Exception as e:
        bot_logger.error(f"Error in all_tasks callback: {e}")
        await loading_msg.edit_text(
            "❌ Ошибка получения всех задач",
            parse_mode="MarkdownV2"
        )


@router.callback_query(F.data == "all_projects")
async def callback_all_projects(callback: CallbackQuery):
    """Показать все проекты"""
    admin_id = callback.from_user.id

    if not is_admin(admin_id):
        await callback.answer("❌ У вас нет прав для этого действия", show_alert=True)
        return

    loading_msg = await callback.message.edit_text(
        "📋 Загружаю проекты из Plane\\.\\.\\.\n⏱️ _Это займет \\~15 секунд_",
        parse_mode="MarkdownV2"
    )

    try:
        from ...services.daily_tasks_service import daily_tasks_service

        if not daily_tasks_service or not plane_api.configured:
            await loading_msg.edit_text(
                "❌ Plane API не настроен",
                parse_mode="MarkdownV2"
            )
            return

        await daily_tasks_service._load_admin_settings_from_db()
        admin_settings = daily_tasks_service.admin_settings.get(admin_id, {})

        admin_email = admin_settings.get('plane_email')
        if not admin_email:
            await loading_msg.edit_text(
                "📧 Email не настроен\n\n"
                "Сначала настройте email для получения задач\\.",
                parse_mode="MarkdownV2"
            )
            return

        bot_logger.info(f"🔄 Fetching tasks from Plane API for projects view for {admin_email}")
        all_tasks = await plane_api.get_user_tasks(admin_email)
        bot_logger.info(f"✅ Retrieved {len(all_tasks)} tasks from Plane API")

        if not all_tasks:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 Все задачи", callback_data=f"all_tasks_{admin_id}")],
                [InlineKeyboardButton(text="🏠 В главное меню", callback_data="start_menu")]
            ])
            await loading_msg.edit_text(
                "❌ Проекты не найдены\n\n"
                "У вас нет активных задач в Plane\\.",
                reply_markup=keyboard,
                parse_mode="MarkdownV2"
            )
            return

        # Получаем уникальные названия проектов
        projects_set = set(task.project_name for task in all_tasks)
        projects_list = sorted(list(projects_set))

        keyboard_buttons = []
        # Показываем ВСЕ проекты (убран лимит [:20])
        for project_name in projects_list:
            tasks_count = sum(1 for task in all_tasks if task.project_name == project_name)
            display_name = project_name[:30] + "..." if len(project_name) > 30 else project_name

            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"📁 {display_name} ({tasks_count})",
                    callback_data=f"project_{project_name}"
                )
            ])

        keyboard_buttons.extend([
            [InlineKeyboardButton(text="📋 Все задачи", callback_data=f"all_tasks_{admin_id}")],
            [InlineKeyboardButton(text="🏠 В главное меню", callback_data="start_menu")]
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        projects_count = len(projects_list)
        shown_count = projects_count

        await loading_msg.edit_text(
            f"📁 *Проекты из Plane*\n\n"
            f"📊 Всего проектов: {projects_count}\n"
            f"👁 Показано: {shown_count}\n\n"
            f"Выберите проект для просмотра задач:",
            reply_markup=keyboard,
            parse_mode="MarkdownV2"
        )

    except Exception as e:
        bot_logger.error(f"Error in all_projects callback: {e}")
        await loading_msg.edit_text(
            "❌ Ошибка загрузки проектов",
            parse_mode="MarkdownV2"
        )

    await callback.answer()


@router.callback_query(F.data.startswith("project_"))
async def callback_project_tasks(callback: CallbackQuery):
    """Показать задачи конкретного проекта"""
    admin_id = callback.from_user.id

    if not is_admin(admin_id):
        await callback.answer("❌ У вас нет прав для этого действия", show_alert=True)
        return

    project_name_raw = callback.data.replace("project_", "")

    loading_msg = await callback.message.edit_text(
        "📋 Загружаю задачи из Plane\\.\\.\\.\n⏱️ _Это займет \\~15 секунд_",
        parse_mode="MarkdownV2"
    )

    try:
        from ...services.daily_tasks_service import daily_tasks_service

        if not daily_tasks_service or not plane_api.configured:
            await loading_msg.edit_text(
                "❌ Plane API не настроен",
                parse_mode="MarkdownV2"
            )
            return

        await daily_tasks_service._load_admin_settings_from_db()
        admin_settings = daily_tasks_service.admin_settings.get(admin_id, {})

        admin_email = admin_settings.get('plane_email')
        if not admin_email:
            await loading_msg.edit_text(
                "📧 Email не настроен",
                parse_mode="MarkdownV2"
            )
            return

        bot_logger.info(f"🔄 Fetching tasks from Plane API for project '{project_name_raw}' for {admin_email}")
        all_tasks = await plane_api.get_user_tasks(admin_email)
        bot_logger.info(f"✅ Retrieved {len(all_tasks)} tasks from Plane API")

        project_tasks = [task for task in all_tasks if task.project_name == project_name_raw]

        if not project_tasks:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ К проектам", callback_data="all_projects")],
                [InlineKeyboardButton(text="📋 Все задачи", callback_data=f"all_tasks_{admin_id}")],
                [InlineKeyboardButton(text="🏠 В главное меню", callback_data="start_menu")]
            ])

            project_name_escaped = escape_markdown_v2(project_name_raw)
            await loading_msg.edit_text(
                f"📁 *Проект:* {project_name_escaped}\n\n"
                f"📭 В проекте нет задач",
                reply_markup=keyboard,
                parse_mode="MarkdownV2"
            )
            return

        project_name_escaped = escape_markdown_v2(project_name_raw)
        tasks_text = f"📁 *Проект:* {project_name_escaped}\n\n"
        tasks_text += f"📊 *Задач в проекте:* {len(project_tasks)}\n\n"

        for i, task in enumerate(project_tasks, 1):
            state_emoji = task.state_emoji
            priority_emoji = task.priority_emoji
            task_name = escape_markdown_v2(task.name)
            task_url = task.task_url
            status_text = escape_markdown_v2(task.state_name or 'Неизвестно')
            project_escaped = escape_markdown_v2(task.project_name)

            tasks_text += f"{i}\\. {state_emoji} {priority_emoji} [{task_name}]({task_url})\n"
            tasks_text += f"   📁 {project_escaped} \\| 🏷️ {status_text}\n\n"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ К проектам", callback_data="all_projects")],
            [InlineKeyboardButton(text="📋 Все задачи", callback_data=f"all_tasks_{admin_id}")],
            [InlineKeyboardButton(text="🏠 В главное меню", callback_data="start_menu")]
        ])

        from aiogram.types import LinkPreviewOptions

        await loading_msg.edit_text(
            tasks_text,
            reply_markup=keyboard,
            parse_mode="MarkdownV2",
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )

    except Exception as e:
        bot_logger.error(f"Error in project_tasks callback: {e}")
        await loading_msg.edit_text(
            "❌ Ошибка загрузки задач проекта",
            parse_mode="MarkdownV2"
        )

    await callback.answer()
