"""
Обработчики навигации для работы с задачами и проектами
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict, Any

from .filters import IsAdminFilter
from ...integrations.plane import plane_api
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


@router.callback_query(F.data.startswith("all_tasks_"))
async def callback_all_tasks(callback: CallbackQuery):
    """Показать все задачи админа из КЭША с группировкой по проектам"""
    admin_id = callback.from_user.id

    if not is_admin(admin_id):
        await callback.answer("❌ У вас нет прав для этого действия", show_alert=True)
        return

    loading_msg = await callback.message.edit_text(
        "📋 Загружаю задачи из кэша\\.\\.\\.",
        parse_mode="MarkdownV2"
    )

    try:
        from ...services.daily_tasks_service import daily_tasks_service
        from ...services.user_tasks_cache_service import user_tasks_cache_service

        if not daily_tasks_service:
            await loading_msg.edit_text(
                "❌ Сервис задач не настроен",
                parse_mode="MarkdownV2"
            )
            return

        # Загружаем настройки админа
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

        # 🚀 Получаем задачи из КЭША (быстро!)
        cached_tasks = await user_tasks_cache_service.get_cached_tasks(
            user_email=admin_email,
            include_overdue=True,
            include_today=True,
            include_upcoming=True,
            max_tasks=100  # Показываем до 100 задач
        )

        if not cached_tasks:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить данные", callback_data="refresh_tasks")],
                [InlineKeyboardButton(text="🏠 В главное меню", callback_data="start_menu")]
            ])
            await loading_msg.edit_text(
                f"📋 *Все задачи из Plane*\n\n"
                f"👤 Email: {escape_markdown_v2(admin_email)}\n"
                f"📊 Найдено задач: 0\n\n"
                f"У вас нет активных задач в кэше\\. Обновите данные\\.",
                reply_markup=keyboard,
                parse_mode="MarkdownV2"
            )
            return

        # Группируем задачи по проектам
        tasks_by_project = {}
        for task in cached_tasks:
            project_name = task.project_name
            if project_name not in tasks_by_project:
                tasks_by_project[project_name] = []
            tasks_by_project[project_name].append(task)

        # Формируем красивый вывод
        admin_email_escaped = escape_markdown_v2(admin_email)
        tasks_text = f"📋 *Все задачи из Plane*\n\n"
        tasks_text += f"👤 *Email:* {admin_email_escaped}\n"
        tasks_text += f"📊 *Всего задач:* {len(cached_tasks)}\n"
        tasks_text += f"📁 *Проектов:* {len(tasks_by_project)}\n\n"

        task_counter = 1
        for project_name, project_tasks in tasks_by_project.items():
            project_name_escaped = escape_markdown_v2(project_name)
            tasks_text += f"📁 *{project_name_escaped}* \\({len(project_tasks)} задач\\)\n"

            # Показываем ВСЕ задачи из проекта (без лимита)
            for task in project_tasks:
                state_emoji = task.state_emoji
                priority_emoji = task.priority_emoji
                task_name = escape_markdown_v2(task.title)
                task_url = task.task_url

                # Используем название СО ССЫЛКОЙ (предпросмотр отключен ниже)
                tasks_text += f"  {task_counter}\\. {state_emoji} {priority_emoji} [{task_name}]({task_url})\n"
                task_counter += 1

            tasks_text += "\n"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📁 По проектам", callback_data="all_projects")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="daily_tasks"),
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
        bot_logger.error(f"Error in all_tasks callback: {e}")
        await loading_msg.edit_text(
            "❌ Ошибка получения всех задач",
            parse_mode="MarkdownV2"
        )


@router.callback_query(F.data == "all_projects")
async def callback_all_projects(callback: CallbackQuery):
    """Показать все проекты из КЭША"""
    admin_id = callback.from_user.id

    if not is_admin(admin_id):
        await callback.answer("❌ У вас нет прав для этого действия", show_alert=True)
        return

    try:
        from ...services.daily_tasks_service import daily_tasks_service
        from ...services.user_tasks_cache_service import user_tasks_cache_service

        # Загружаем настройки админа
        await daily_tasks_service._load_admin_settings_from_db()
        admin_settings = daily_tasks_service.admin_settings.get(admin_id, {})

        admin_email = admin_settings.get('plane_email')
        if not admin_email:
            await callback.message.edit_text(
                "📧 Email не настроен",
                parse_mode="MarkdownV2"
            )
            return

        # Получаем все задачи из кэша
        all_tasks = await user_tasks_cache_service.get_cached_tasks(
            user_email=admin_email,
            include_overdue=True,
            include_today=True,
            include_upcoming=True,
            max_tasks=100
        )

        if not all_tasks:
            await callback.message.edit_text(
                "❌ Проекты не найдены в кэше\n\n"
                "Обновите данные\\.",
                parse_mode="MarkdownV2"
            )
            return

        # Получаем уникальные названия проектов из кэша
        projects_set = set(task.project_name for task in all_tasks)
        projects_list = sorted(list(projects_set))

        # Создаем кнопки для проектов (по 1 в ряд)
        keyboard_buttons = []

        for project_name in projects_list[:20]:
            # Подсчитываем количество задач в проекте
            tasks_count = sum(1 for task in all_tasks if task.project_name == project_name)

            # Ограничиваем длину названия для кнопки
            display_name = project_name[:30] + "..." if len(project_name) > 30 else project_name

            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"📁 {display_name} ({tasks_count})",
                    callback_data=f"project_{project_name}"
                )
            ])

        # Добавляем кнопки навигации
        keyboard_buttons.extend([
            [InlineKeyboardButton(text="📋 Все задачи", callback_data=f"all_tasks_{admin_id}")],
            [InlineKeyboardButton(text="🏠 В главное меню", callback_data="start_menu")]
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        projects_count = len(projects_list)
        shown_count = min(20, projects_count)

        await callback.message.edit_text(
            f"📁 *Проекты в кэше*\n\n"
            f"📊 Всего проектов: {projects_count}\n"
            f"👁 Показано: {shown_count}\n\n"
            f"Выберите проект для просмотра задач:",
            reply_markup=keyboard,
            parse_mode="MarkdownV2"
        )

    except Exception as e:
        bot_logger.error(f"Error in all_projects callback: {e}")
        await callback.message.edit_text(
            "❌ Ошибка загрузки проектов",
            parse_mode="MarkdownV2"
        )

    await callback.answer()


@router.callback_query(F.data.startswith("project_"))
async def callback_project_tasks(callback: CallbackQuery):
    """Показать задачи конкретного проекта из КЭША"""
    admin_id = callback.from_user.id

    if not is_admin(admin_id):
        await callback.answer("❌ У вас нет прав для этого действия", show_alert=True)
        return

    # Извлекаем название проекта из callback_data (формат: "project_PROJECT_NAME")
    project_name_raw = callback.data.replace("project_", "")

    await callback.message.edit_text("📋 Загружаю задачи из кэша\\.\\.\\.", parse_mode="MarkdownV2")

    try:
        from ...services.daily_tasks_service import daily_tasks_service
        from ...services.user_tasks_cache_service import user_tasks_cache_service

        # Загружаем настройки админа
        await daily_tasks_service._load_admin_settings_from_db()
        admin_settings = daily_tasks_service.admin_settings.get(admin_id, {})

        admin_email = admin_settings.get('plane_email')
        if not admin_email:
            await callback.message.edit_text(
                "📧 Email не настроен",
                parse_mode="MarkdownV2"
            )
            return

        # Получаем ВСЕ задачи из кэша
        all_tasks = await user_tasks_cache_service.get_cached_tasks(
            user_email=admin_email,
            include_overdue=True,
            include_today=True,
            include_upcoming=True,
            max_tasks=100
        )

        # Фильтруем задачи по названию проекта
        project_tasks = [task for task in all_tasks if task.project_name == project_name_raw]

        if not project_tasks:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ К проектам", callback_data="all_projects")],
                [InlineKeyboardButton(text="📋 Все задачи", callback_data=f"all_tasks_{admin_id}")],
                [InlineKeyboardButton(text="🏠 В главное меню", callback_data="start_menu")]
            ])

            project_name_escaped = escape_markdown_v2(project_name_raw)
            await callback.message.edit_text(
                f"📁 *Проект:* {project_name_escaped}\n\n"
                f"📭 В проекте нет задач в кэше",
                reply_markup=keyboard,
                parse_mode="MarkdownV2"
            )
            return

        # Формируем список задач проекта
        project_name_escaped = escape_markdown_v2(project_name_raw)
        tasks_text = f"📁 *Проект:* {project_name_escaped}\n\n"
        tasks_text += f"📊 *Задач в проекте:* {len(project_tasks)}\n\n"

        for i, task in enumerate(project_tasks, 1):
            state_emoji = task.state_emoji
            priority_emoji = task.priority_emoji
            task_name = escape_markdown_v2(task.title)
            task_url = task.task_url
            status_text = escape_markdown_v2(task.state_name or 'Неизвестно')

            tasks_text += f"{i}\\. {state_emoji} {priority_emoji} [{task_name}]({task_url})\n"
            tasks_text += f"   🏷️ _{status_text}_\n\n"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ К проектам", callback_data="all_projects")],
            [InlineKeyboardButton(text="📋 Все задачи", callback_data=f"all_tasks_{admin_id}")],
            [InlineKeyboardButton(text="🏠 В главное меню", callback_data="start_menu")]
        ])

        # Отключаем предпросмотр ссылок
        from aiogram.types import LinkPreviewOptions

        await callback.message.edit_text(
            tasks_text,
            reply_markup=keyboard,
            parse_mode="MarkdownV2",
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )

    except Exception as e:
        bot_logger.error(f"Error in project_tasks callback: {e}")
        await callback.message.edit_text(
            "❌ Ошибка загрузки задач проекта",
            parse_mode="MarkdownV2"
        )

    await callback.answer()


async def show_grouped_tasks(callback: CallbackQuery, project_id: str, project_name: str, tasks: List[Any]):
    """Показать сгруппированные задачи по приоритетам"""
    # Группируем по приоритету
    groups = {
        'urgent': [],
        'high': [],
        'medium': [],
        'low': [],
        'none': []
    }
    
    for task in tasks:
        priority = task.priority.lower()
        if priority in groups:
            groups[priority].append(task)
        else:
            groups['none'].append(task)
    
    # Создаем кнопки для групп с задачами
    keyboard_buttons = []
    
    group_names = {
        'urgent': '🔴 Критичные',
        'high': '🟠 Высокий приоритет', 
        'medium': '🟡 Средний приоритет',
        'low': '🟢 Низкий приоритет',
        'none': '⚪ Без приоритета'
    }
    
    for priority, group_tasks in groups.items():
        if group_tasks:
            group_name = group_names[priority]
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"{group_name} ({len(group_tasks)})",
                    callback_data=f"group_{project_id}_{priority}"
                )
            ])
    
    # Добавляем кнопки навигации
    keyboard_buttons.extend([
        [InlineKeyboardButton(text="📋 Все задачи списком", callback_data=f"list_{project_id}")],
        [InlineKeyboardButton(text="⬅️ К проектам", callback_data="all_projects")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="start_menu")]
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    project_name_escaped = escape_markdown_v2(project_name)
    await callback.message.edit_text(
        f"📁 *Проект:* {project_name_escaped}\n\n"
        f"📊 Всего задач: {len(tasks)}\n\n"
        f"Задачи сгруппированы по приоритету:",
        reply_markup=keyboard,
        parse_mode="MarkdownV2"
    )


async def show_tasks_list(callback: CallbackQuery, project_id: str, project_name: str, tasks: List[Any]):
    """Показать список задач"""
    keyboard_buttons = []
    
    # Создаем кнопки для задач
    for i, task in enumerate(tasks[:10], 1):  # Максимум 10 задач
        task_title = task.name[:40] + "..." if len(task.name) > 40 else task.name
        
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{task.state_emoji} {task.priority_emoji} {task_title}",
                callback_data=f"task_{project_id}_{task.id}"
            )
        ])
    
    # Добавляем кнопки навигации
    keyboard_buttons.extend([
        [InlineKeyboardButton(text="⬅️ К проектам", callback_data="all_projects")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="start_menu")]
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    project_name_escaped = escape_markdown_v2(project_name)
    tasks_text = f"📁 *Проект:* {project_name_escaped}\n\n"
    tasks_text += f"📋 *Задачи проекта:*\n\n"
    
    for i, task in enumerate(tasks[:10], 1):
        assignee = "Не назначен" if not task.assignee_details else task.assignee_name
        assignee_escaped = escape_markdown_v2(assignee)
        task_name_escaped = escape_markdown_v2(task.name)
        
        tasks_text += f"{i}\\. {task.state_emoji} {task.priority_emoji} {task_name_escaped}\n"
        tasks_text += f"   👤 {assignee_escaped} | 🏷️ {task.state_name}\n"
        if task.target_date:
            date_escaped = escape_markdown_v2(task.target_date[:10])  # Только дата
            tasks_text += f"   📅 {date_escaped}\n"
        tasks_text += "\n"
    
    if len(tasks) > 10:
        tasks_text += f"\\.\\.\\. и еще {len(tasks) - 10} задач"
    
    await callback.message.edit_text(
        tasks_text,
        reply_markup=keyboard,
        parse_mode="MarkdownV2"
    )


@router.callback_query(F.data.startswith("group_"))
async def callback_task_group(callback: CallbackQuery):
    """Показать задачи конкретной группы приоритета"""
    admin_id = callback.from_user.id
    
    if not is_admin(admin_id):
        await callback.answer("❌ У вас нет прав для этого действия", show_alert=True)
        return
    
    # Парсим callback data: group_{project_id}_{priority}
    parts = callback.data.replace("group_", "").split("_")
    if len(parts) < 2:
        await callback.answer("❌ Неверный формат данных", show_alert=True)
        return
    
    project_id = parts[0]
    priority = parts[1]
    
    await callback.message.edit_text("🔄 Загружаю задачи группы\\.\\.\\.", parse_mode="MarkdownV2")
    
    try:
        # Получаем информацию о проекте и задачи
        projects = await plane_api.get_all_projects()
        project_info = next((p for p in projects if p.get('id') == project_id), None)
        
        if not project_info:
            await callback.message.edit_text(
                "❌ Проект не найден",
                parse_mode="MarkdownV2"
            )
            return
        
        project_name = project_info.get('name', 'Unknown')
        all_tasks = await plane_api.get_project_tasks(project_id, include_subtasks=True)
        
        # Фильтруем задачи по приоритету
        group_tasks = [task for task in all_tasks if task.priority.lower() == priority]
        
        if not group_tasks:
            await callback.message.edit_text(
                f"📭 В группе '{priority}' нет задач",
                parse_mode="MarkdownV2"
            )
            return
        
        await show_tasks_list(callback, project_id, f"{project_name} - {priority.title()}", group_tasks)
        
    except Exception as e:
        bot_logger.error(f"Error in task_group callback: {e}")
        await callback.message.edit_text(
            "❌ Ошибка загрузки задач группы",
            parse_mode="MarkdownV2"
        )
    
    await callback.answer()


@router.callback_query(F.data.startswith("task_"))
async def callback_task_details(callback: CallbackQuery):
    """Показать детали конкретной задачи"""
    admin_id = callback.from_user.id
    
    if not is_admin(admin_id):
        await callback.answer("❌ У вас нет прав для этого действия", show_alert=True)
        return
    
    # Парсим callback data: task_{project_id}_{task_id}
    parts = callback.data.replace("task_", "").split("_", 1)
    if len(parts) < 2:
        await callback.answer("❌ Неверный формат данных", show_alert=True)
        return
    
    project_id = parts[0]
    task_id = parts[1]
    
    await callback.message.edit_text("🔄 Загружаю детали задачи\\.\\.\\.", parse_mode="MarkdownV2")
    
    try:
        task = await plane_api.get_task_details(project_id, task_id)
        
        if not task:
            await callback.message.edit_text(
                "❌ Задача не найдена",
                parse_mode="MarkdownV2"
            )
            return
        
        # Формируем детальную информацию о задаче
        task_name_escaped = escape_markdown_v2(task.name)
        assignee = "Не назначен" if not task.assignee_details else task.assignee_name
        assignee_escaped = escape_markdown_v2(assignee)
        project_name_escaped = escape_markdown_v2(task.project_name)
        state_escaped = escape_markdown_v2(task.state_name)
        
        details_text = f"📋 *Детали задачи*\n\n"
        details_text += f"📝 *Название:* {task_name_escaped}\n\n"
        details_text += f"🏢 *Проект:* {project_name_escaped}\n"
        details_text += f"👤 *Исполнитель:* {assignee_escaped}\n"
        details_text += f"🏷️ *Статус:* {task.state_emoji} {state_escaped}\n"
        details_text += f"🔥 *Приоритет:* {task.priority_emoji} {task.priority.title()}\n"
        
        if task.target_date:
            date_escaped = escape_markdown_v2(task.target_date[:10])
            details_text += f"📅 *Срок:* {date_escaped}"
            if task.is_overdue:
                details_text += " ⚠️ *ПРОСРОЧЕНО*"
            elif task.is_due_today:
                details_text += " 🔥 *СЕГОДНЯ*"
            details_text += "\n"
        
        if task.description:
            desc_escaped = escape_markdown_v2(task.description[:200])
            if len(task.description) > 200:
                desc_escaped += "\\.\\.\\."
            details_text += f"\n📄 *Описание:*\n{desc_escaped}\n"
        
        # Кнопки для навигации
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ К задачам проекта", callback_data=f"project_{project_id}")],
            [InlineKeyboardButton(text="📁 К проектам", callback_data="all_projects")],
            [InlineKeyboardButton(text="🏠 В главное меню", callback_data="start_menu")]
        ])
        
        await callback.message.edit_text(
            details_text,
            reply_markup=keyboard,
            parse_mode="MarkdownV2"
        )
        
    except Exception as e:
        bot_logger.error(f"Error in task_details callback: {e}")
        await callback.message.edit_text(
            "❌ Ошибка загрузки деталей задачи",
            parse_mode="MarkdownV2"
        )
    
    await callback.answer()


@router.callback_query(F.data.startswith("list_"))
async def callback_list_all_tasks(callback: CallbackQuery):
    """Показать все задачи проекта списком"""
    admin_id = callback.from_user.id
    
    if not is_admin(admin_id):
        await callback.answer("❌ У вас нет прав для этого действия", show_alert=True)
        return
    
    project_id = callback.data.replace("list_", "")
    
    await callback.message.edit_text("🔄 Загружаю полный список задач\\.\\.\\.", parse_mode="MarkdownV2")
    
    try:
        # Получаем информацию о проекте и задачи
        projects = await plane_api.get_all_projects()
        project_info = next((p for p in projects if p.get('id') == project_id), None)
        
        if not project_info:
            await callback.message.edit_text(
                "❌ Проект не найден",
                parse_mode="MarkdownV2"
            )
            return
        
        project_name = project_info.get('name', 'Unknown')
        tasks = await plane_api.get_project_tasks(project_id, include_subtasks=True)
        
        await show_tasks_list(callback, project_id, project_name, tasks)
        
    except Exception as e:
        bot_logger.error(f"Error in list_all_tasks callback: {e}")
        await callback.message.edit_text(
            "❌ Ошибка загрузки списка задач",
            parse_mode="MarkdownV2"
        )
    
    await callback.answer()


@router.callback_query(F.data == "my_tasks")
async def callback_my_tasks(callback: CallbackQuery):
    """Показать мои назначенные задачи"""
    admin_id = callback.from_user.id
    
    if not is_admin(admin_id):
        await callback.answer("❌ У вас нет прав для этого действия", show_alert=True)
        return
    
    await callback.message.edit_text("🔄 Загружаю ваши задачи\\.\\.\\.", parse_mode="MarkdownV2")
    
    try:
        # Получаем задачи для админа
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
        
        # Группируем задачи по проектам если их больше 10
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
    # Группируем по проектам
    projects_tasks = {}
    for task in tasks:
        project_name = task.project_name
        if project_name not in projects_tasks:
            projects_tasks[project_name] = []
        projects_tasks[project_name].append(task)
    
    # Создаем кнопки для проектов
    keyboard_buttons = []
    
    for project_name, project_tasks in projects_tasks.items():
        # Ограничиваем длину названия проекта
        display_name = project_name[:35] + "..." if len(project_name) > 35 else project_name
        
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"📁 {display_name} ({len(project_tasks)})",
                callback_data=f"my_project_{hash(project_name) % 10000}"  # Используем хэш для короткого ID
            )
        ])
    
    # Добавляем кнопки навигации
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
    
    # Создаем кнопки для задач
    for i, task in enumerate(tasks[:10], 1):  # Максимум 10 задач
        task_title = task.name[:35] + "..." if len(task.name) > 35 else task.name
        
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{task.state_emoji} {task.priority_emoji} {task_title}",
                callback_data=f"my_task_{task.project_detail.get('id', 'unknown')}_{task.id}"
            )
        ])
    
    # Добавляем кнопки навигации
    keyboard_buttons.extend([
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="start_menu")]
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    tasks_text = f"👤 *Мои назначенные задачи*\n\n"
    
    for i, task in enumerate(tasks[:10], 1):
        task_name_escaped = escape_markdown_v2(task.name)
        project_escaped = escape_markdown_v2(task.project_name)
        
        tasks_text += f"{i}\\. {task.state_emoji} {task.priority_emoji} {task_name_escaped}\n"
        tasks_text += f"   📁 {project_escaped} | 🏷️ {task.state_name}\n"
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