"""
Admin handlers for managing chat-project mappings
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from ...middleware.auth import require_admin
from ...database.database import get_async_session
from ...services.support_requests_service import support_requests_service
from ...integrations.plane import plane_api
from ...utils.logger import bot_logger
from ...utils.markdown import escape_markdown_v2
from ...config import settings


router = Router()


def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return user_id in settings.admin_user_id_list


@require_admin
@router.message(Command("list_mappings"))
async def cmd_list_mappings(message: Message):
    """List all chat-project mappings"""
    admin_id = message.from_user.id

    if not is_admin(admin_id):
        await message.reply("❌ У вас нет прав для выполнения этой команды")
        return

    async for session in get_async_session():
        mappings = await support_requests_service.list_all_mappings(session, only_active=True)

        if not mappings:
            await message.reply(
                "📋 *Настроенные чаты*\n\n"
                "Нет активных привязок чатов к проектам\\.\n\n"
                "_Используйте /setup\\_chat в групповом чате для настройки\\._",
                parse_mode="MarkdownV2"
            )
            return

        text = f"📋 *Настроенные чаты* \\({len(mappings)}\\)\n\n"

        for i, mapping in enumerate(mappings, 1):
            chat_title = escape_markdown_v2(mapping.chat_title or "Unknown")
            project_name = escape_markdown_v2(mapping.plane_project_name or "Unknown")
            chat_id_escaped = escape_markdown_v2(str(mapping.chat_id))

            status_icon = "✅" if mapping.is_active else "❌"

            text += f"{i}\\. {status_icon} *{chat_title}*\n"
            text += f"   📁 Проект: {project_name}\n"
            text += f"   🆔 Chat ID: `{chat_id_escaped}`\n\n"

        await message.reply(text, parse_mode="MarkdownV2")


@require_admin
@router.message(Command("setup_chat"))
async def cmd_setup_chat(message: Message):
    """
    Setup current chat for support requests
    Must be run in a group chat
    """
    admin_id = message.from_user.id
    chat_id = message.chat.id

    if not is_admin(admin_id):
        await message.reply("❌ У вас нет прав для выполнения этой команды")
        return

    # Check if this is a group chat
    if chat_id > 0:
        await message.reply(
            "❌ Эта команда работает только в групповых чатах\\.\n\n"
            "Запустите её в групповом чате, который хотите настроить\\.",
            parse_mode="MarkdownV2"
        )
        return

    async for session in get_async_session():
        # Check if mapping already exists
        existing = await support_requests_service.get_chat_mapping(session, chat_id)
        if existing:
            project_escaped = escape_markdown_v2(existing.plane_project_name)
            await message.reply(
                f"ℹ️ *Чат уже настроен*\n\n"
                f"📁 Текущий проект: {project_escaped}\n\n"
                f"Используйте /remove\\_chat для удаления настройки\\.",
                parse_mode="MarkdownV2"
            )
            return

        # Get list of projects from Plane
        try:
            projects = await plane_api.get_all_projects()

            if not projects:
                await message.reply(
                    "❌ Не удалось получить список проектов из Plane\\.\n\n"
                    "Проверьте настройки Plane API\\.",
                    parse_mode="MarkdownV2"
                )
                return

            # Show project selection - use index instead of UUID to avoid BUTTON_DATA_INVALID
            # Show all projects with pagination if needed
            keyboard_rows = []

            # Show up to 25 projects on first page
            projects_to_show = projects[:25]

            for idx, project in enumerate(projects_to_show):
                project_name = project.get('name', 'Unknown')

                # Use short index instead of long UUID
                keyboard_rows.append([
                    InlineKeyboardButton(
                        text=f"📁 {project_name[:35]}",
                        callback_data=f"sproj_{chat_id}_{idx}"  # Short prefix + index
                    )
                ])

            # Add pagination if more than 25 projects
            if len(projects) > 25:
                keyboard_rows.append([
                    InlineKeyboardButton(text="➡️ Показать ещё", callback_data=f"ppage_{chat_id}_1")
                ])

            keyboard_rows.append([
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_setup")
            ])

            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

            projects_count = len(projects)
            showing_count = min(25, projects_count)

            await message.reply(
                f"📁 *Выберите проект Plane для этого чата:*\n\n"
                f"_Показано {showing_count} из {projects_count} проектов_",
                reply_markup=keyboard,
                parse_mode="MarkdownV2"
            )

        except Exception as e:
            bot_logger.error(f"Error getting projects for setup: {e}")
            await message.reply(
                "❌ Ошибка при получении списка проектов\\.",
                parse_mode="MarkdownV2"
            )


@router.callback_query(F.data.startswith("sproj_"))
async def process_project_selection(callback: CallbackQuery):
    """Process project selection for chat mapping"""
    admin_id = callback.from_user.id

    if not is_admin(admin_id):
        await callback.answer("❌ У вас нет прав", show_alert=True)
        return

    # Parse callback data: sproj_{chat_id}_{index}
    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.answer("❌ Неверный формат данных", show_alert=True)
        return

    try:
        chat_id = int(parts[1])
        project_index = int(parts[2])
    except ValueError:
        await callback.answer("❌ Неверный формат данных", show_alert=True)
        return

    # Get project details
    async for session in get_async_session():
        try:
            projects = await plane_api.get_all_projects()

            if project_index >= len(projects):
                await callback.answer("❌ Проект не найден", show_alert=True)
                return

            project = projects[project_index]
            project_id = project.get('id', '')
            project_name = project.get('name', 'Unknown')

            # Get chat info
            chat = await callback.bot.get_chat(chat_id)
            chat_title = chat.title or "Unknown"
            chat_type = chat.type

            # Create mapping
            mapping = await support_requests_service.create_chat_mapping(
                session=session,
                chat_id=chat_id,
                chat_title=chat_title,
                chat_type=chat_type,
                plane_project_id=project_id,
                plane_project_name=project_name,
                created_by=admin_id
            )

            chat_title_escaped = escape_markdown_v2(chat_title)
            project_name_escaped = escape_markdown_v2(project_name)

            await callback.message.edit_text(
                f"✅ *Чат успешно настроен\\!*\n\n"
                f"💬 *Чат:* {chat_title_escaped}\n"
                f"📁 *Проект:* {project_name_escaped}\n\n"
                f"Теперь пользователи могут создавать заявки через команду /new\\_request",
                parse_mode="MarkdownV2"
            )

            await callback.answer("✅ Настройка сохранена")

        except Exception as e:
            bot_logger.error(f"Error creating chat mapping: {e}")
            await callback.message.edit_text(
                "❌ Ошибка при создании привязки чата\\.",
                parse_mode="MarkdownV2"
            )
            await callback.answer("❌ Ошибка")


@require_admin
@router.message(Command("remove_chat"))
async def cmd_remove_chat(message: Message):
    """Remove chat mapping (deactivate)"""
    admin_id = message.from_user.id
    chat_id = message.chat.id

    if not is_admin(admin_id):
        await message.reply("❌ У вас нет прав для выполнения этой команды")
        return

    if chat_id > 0:
        await message.reply(
            "❌ Эта команда работает только в групповых чатах\\.",
            parse_mode="MarkdownV2"
        )
        return

    async for session in get_async_session():
        # Check if mapping exists
        mapping = await support_requests_service.get_chat_mapping(session, chat_id)
        if not mapping:
            await message.reply(
                "ℹ️ Этот чат не настроен для заявок\\.",
                parse_mode="MarkdownV2"
            )
            return

        # Confirm deletion
        project_escaped = escape_markdown_v2(mapping.plane_project_name)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_remove_{chat_id}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_remove")
            ]
        ])

        await message.reply(
            f"❓ *Удалить настройку чата?*\n\n"
            f"📁 Текущий проект: {project_escaped}\n\n"
            f"_Пользователи больше не смогут создавать заявки из этого чата\\._",
            reply_markup=keyboard,
            parse_mode="MarkdownV2"
        )


@router.callback_query(F.data.startswith("confirm_remove_"))
async def confirm_remove_chat(callback: CallbackQuery):
    """Confirm chat mapping removal"""
    admin_id = callback.from_user.id

    if not is_admin(admin_id):
        await callback.answer("❌ У вас нет прав", show_alert=True)
        return

    chat_id = int(callback.data.replace("confirm_remove_", ""))

    async for session in get_async_session():
        success = await support_requests_service.delete_chat_mapping(session, chat_id)

        if success:
            await callback.message.edit_text(
                "✅ Настройка чата удалена\\.",
                parse_mode="MarkdownV2"
            )
            await callback.answer("✅ Удалено")
        else:
            await callback.message.edit_text(
                "❌ Ошибка при удалении настройки\\.",
                parse_mode="MarkdownV2"
            )
            await callback.answer("❌ Ошибка")


@router.callback_query(F.data.startswith("ppage_"))
async def show_project_page(callback: CallbackQuery):
    """Show next page of projects"""
    admin_id = callback.from_user.id

    if not is_admin(admin_id):
        await callback.answer("❌ У вас нет прав", show_alert=True)
        return

    # Parse callback data: ppage_{chat_id}_{page}
    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.answer("❌ Неверный формат данных", show_alert=True)
        return

    try:
        chat_id = int(parts[1])
        page = int(parts[2])
    except ValueError:
        await callback.answer("❌ Неверный формат данных", show_alert=True)
        return

    async for session in get_async_session():
        try:
            projects = await plane_api.get_all_projects()

            # Calculate pagination
            page_size = 25
            start_idx = page * page_size
            end_idx = start_idx + page_size

            if start_idx >= len(projects):
                await callback.answer("❌ Страница не найдена", show_alert=True)
                return

            projects_to_show = projects[start_idx:end_idx]

            keyboard_rows = []
            for idx, project in enumerate(projects_to_show, start=start_idx):
                project_name = project.get('name', 'Unknown')
                keyboard_rows.append([
                    InlineKeyboardButton(
                        text=f"📁 {project_name[:35]}",
                        callback_data=f"sproj_{chat_id}_{idx}"
                    )
                ])

            # Navigation buttons
            nav_buttons = []
            if page > 0:
                nav_buttons.append(
                    InlineKeyboardButton(text="⬅️ Назад", callback_data=f"ppage_{chat_id}_{page-1}")
                )
            if end_idx < len(projects):
                nav_buttons.append(
                    InlineKeyboardButton(text="➡️ Далее", callback_data=f"ppage_{chat_id}_{page+1}")
                )

            if nav_buttons:
                keyboard_rows.append(nav_buttons)

            keyboard_rows.append([
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_setup")
            ])

            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

            showing_from = start_idx + 1
            showing_to = min(end_idx, len(projects))
            total = len(projects)

            await callback.message.edit_text(
                f"📁 *Выберите проект Plane для этого чата:*\n\n"
                f"_Показано {showing_from}\\-{showing_to} из {total} проектов_",
                reply_markup=keyboard,
                parse_mode="MarkdownV2"
            )
            await callback.answer()

        except Exception as e:
            bot_logger.error(f"Error showing project page: {e}")
            await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.in_(["cancel_setup", "cancel_remove"]))
async def cancel_admin_action(callback: CallbackQuery):
    """Cancel admin action"""
    await callback.message.edit_text(
        "❌ Действие отменено\\.",
        parse_mode="MarkdownV2"
    )
    await callback.answer()


@require_admin
@router.message(Command("requests_stats"))
async def cmd_requests_stats(message: Message):
    """Show support requests statistics"""
    admin_id = message.from_user.id

    if not is_admin(admin_id):
        await message.reply("❌ У вас нет прав для выполнения этой команды")
        return

    async for session in get_async_session():
        # Get pending requests count
        pending_count = await support_requests_service.get_pending_requests_count(session)

        # Get all mappings count
        mappings = await support_requests_service.list_all_mappings(session, only_active=True)
        mappings_count = len(mappings)

        await message.reply(
            f"📊 *Статистика заявок*\n\n"
            f"💬 *Настроенных чатов:* {mappings_count}\n"
            f"⏳ *Заявок в обработке:* {pending_count}\n\n"
            f"_Используйте /list\\_mappings для просмотра чатов\\._",
            parse_mode="MarkdownV2"
        )
