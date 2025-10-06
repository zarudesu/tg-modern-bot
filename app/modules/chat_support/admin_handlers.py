"""
Admin commands for chat support configuration
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from ...middleware.auth import require_admin
from ...database.database import get_async_session
from ...services.support_requests_service import support_requests_service
from ...integrations.plane import plane_api
from ...utils.logger import bot_logger
from ...config import settings


router = Router(name="chat_support_admin")


def escape_md(text: str) -> str:
    """Escape MarkdownV2 special chars"""
    chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in chars:
        text = text.replace(char, f'\\{char}')
    return text


@require_admin
@router.message(Command("setup_chat"))
async def cmd_setup_chat(message: Message):
    """Setup current chat for support requests (group only)"""
    chat_id = message.chat.id

    bot_logger.info(f"⚙️ SETUP_CHAT: chat={chat_id}, admin={message.from_user.id}")

    if chat_id > 0:
        await message.reply(
            "❌ Эта команда работает только в групповых чатах.\n\n"
            "Запустите её в чате, который хотите настроить.",
            parse_mode="Markdown"
        )
        return

    async for session in get_async_session():
        # Check existing
        existing = await support_requests_service.get_chat_mapping(session, chat_id)
        if existing:
            await message.reply(
                f"ℹ️ **Чат уже настроен**\n\n"
                f"📁 Проект: {existing.plane_project_name}\n\n"
                f"Используйте /remove_chat для удаления.",
                parse_mode="Markdown"
            )
            return

        # Get projects
        try:
            projects = await plane_api.get_all_projects()
            if not projects:
                await message.reply("❌ Не удалось получить список проектов из Plane.")
                return

            # Show first 20 projects
            keyboard_rows = []
            for idx, project in enumerate(projects[:20]):
                keyboard_rows.append([
                    InlineKeyboardButton(
                        text=f"📁 {project['name'][:35]}",
                        callback_data=f"csp_{chat_id}_{idx}"
                    )
                ])

            if len(projects) > 20:
                keyboard_rows.append([
                    InlineKeyboardButton(text="➡️ Ещё", callback_data=f"cspage_{chat_id}_1")
                ])

            keyboard_rows.append([
                InlineKeyboardButton(text="❌ Отмена", callback_data="cs_cancel")
            ])

            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

            await message.reply(
                f"📁 **Выберите проект для этого чата:**\n\n"
                f"Показано {min(20, len(projects))} из {len(projects)} проектов",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )

        except Exception as e:
            bot_logger.error(f"Error getting projects: {e}")
            await message.reply("❌ Ошибка при получении списка проектов.")


@router.callback_query(F.data.startswith("csp_"))
async def process_project_selection(callback: CallbackQuery):
    """Process project selection"""
    if callback.from_user.id not in settings.admin_user_id_list:
        await callback.answer("❌ Только админы", show_alert=True)
        return

    parts = callback.data.split("_")
    chat_id = int(parts[1])
    project_idx = int(parts[2])

    async for session in get_async_session():
        try:
            projects = await plane_api.get_all_projects()
            project = projects[project_idx]

            # Get chat info
            chat = await callback.bot.get_chat(chat_id)

            # Create mapping
            await support_requests_service.create_chat_mapping(
                session=session,
                chat_id=chat_id,
                chat_title=chat.title or "Unknown",
                chat_type=chat.type,
                plane_project_id=project['id'],
                plane_project_name=project['name'],
                created_by=callback.from_user.id
            )

            await callback.message.edit_text(
                f"✅ **Чат настроен!**\n\n"
                f"💬 Чат: {chat.title}\n"
                f"📁 Проект: {project['name']}\n\n"
                f"Пользователи могут создавать заявки через /request",
                parse_mode="Markdown"
            )
            await callback.answer("✅ Готово")

            bot_logger.info(f"✅ Chat mapped: {chat_id} -> {project['name']}")

        except Exception as e:
            bot_logger.error(f"Error creating mapping: {e}")
            await callback.message.edit_text("❌ Ошибка при настройке чата.")
            await callback.answer("❌ Ошибка")


@require_admin
@router.message(Command("remove_chat"))
async def cmd_remove_chat(message: Message):
    """Remove chat mapping"""
    chat_id = message.chat.id

    if chat_id > 0:
        await message.reply("❌ Только в групповых чатах.")
        return

    async for session in get_async_session():
        mapping = await support_requests_service.get_chat_mapping(session, chat_id)
        if not mapping:
            await message.reply("ℹ️ Чат не настроен.")
            return

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data=f"csrm_{chat_id}"),
                InlineKeyboardButton(text="❌ Нет", callback_data="cs_cancel")
            ]
        ])

        await message.reply(
            f"❓ **Удалить настройку?**\n\n"
            f"📁 Проект: {mapping.plane_project_name}\n\n"
            f"Пользователи не смогут создавать заявки.",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )


@router.callback_query(F.data.startswith("csrm_"))
async def confirm_remove(callback: CallbackQuery):
    """Confirm removal"""
    if callback.from_user.id not in settings.admin_user_id_list:
        await callback.answer("❌ Только админы", show_alert=True)
        return

    chat_id = int(callback.data.replace("csrm_", ""))

    async for session in get_async_session():
        success = await support_requests_service.delete_chat_mapping(session, chat_id)

        if success:
            await callback.message.edit_text("✅ Настройка удалена.")
            await callback.answer("✅")
        else:
            await callback.message.edit_text("❌ Ошибка.")
            await callback.answer("❌")


@require_admin
@router.message(Command("list_chats"))
async def cmd_list_chats(message: Message):
    """List all configured chats"""
    async for session in get_async_session():
        mappings = await support_requests_service.list_all_mappings(session, only_active=True)

        if not mappings:
            await message.reply(
                "📋 **Настроенные чаты**\n\n"
                "Нет активных настроек.\n\n"
                "Используйте /setup_chat в группе.",
                parse_mode="Markdown"
            )
            return

        text = f"📋 **Настроенные чаты** ({len(mappings)})\n\n"

        for i, m in enumerate(mappings, 1):
            text += f"{i}. {m.chat_title}\n"
            text += f"   📁 {m.plane_project_name}\n\n"

        await message.reply(text, parse_mode="Markdown")


@router.callback_query(F.data == "cs_cancel")
async def cancel_action(callback: CallbackQuery):
    """Cancel action"""
    await callback.message.edit_text("❌ Отменено.")
    await callback.answer()
