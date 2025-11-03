"""
Simple chat support handlers - just text problem, bot handles the rest
PROPER FSM implementation following aiogram 3 best practices
"""
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from datetime import datetime

from .states import SupportRequestStates
from ...database.database import get_async_session
from ...services.support_requests_service import support_requests_service
from ...utils.logger import bot_logger
from ...config import settings


router = Router(name="chat_support")


@router.message(Command("request"))
async def cmd_request(message: Message, state: FSMContext):
    """
    Simple request creation - just reply with problem description

    Usage in group: /request
    Bot will reply asking for problem description
    User replies with text
    Bot auto-creates ticket in Plane with all context
    """
    user_id = message.from_user.id
    chat_id = message.chat.id

    bot_logger.info(f"📝 REQUEST command: user={user_id}, chat={chat_id}")

    # Check if group chat
    if chat_id > 0:
        await message.reply(
            "❌ Эта команда работает только в групповых чатах.\n\n"
            "Используйте её в чате вашей команды для создания заявки.",
            parse_mode="Markdown"
        )
        return

    # Check if chat is configured
    mapping = None
    async for session in get_async_session():
        mapping = await support_requests_service.get_chat_mapping(session, chat_id)

        if not mapping:
            await message.reply(
                "❌ Этот чат не настроен для заявок.\n\n"
                "Обратитесь к администратору для настройки (/setup_chat).",
                parse_mode="Markdown"
            )
            return

    # Set FSM state with 10 minute timeout
    await state.set_state(SupportRequestStates.waiting_for_problem)

    # Store mapping info in state data with timestamp for timeout check
    from datetime import datetime
    await state.update_data(
        chat_id=chat_id,
        project_name=mapping.plane_project_name,
        request_started_at=datetime.now().timestamp()
    )

    # Send with ForceReply to auto-trigger reply
    await message.reply(
        f"📝 **Создание заявки**\n\n"
        f"📁 Проект: {mapping.plane_project_name}\n\n"
        f"Опишите проблему ниже:",
        reply_markup=ForceReply(selective=True, input_field_placeholder="Опишите проблему..."),
        parse_mode="Markdown"
    )

    bot_logger.info(f"✅ REQUEST prompt sent, FSM state set for user {user_id} in chat {chat_id}")


@router.message(
    SupportRequestStates.waiting_for_problem,
    F.text,
    F.chat.type.in_(["group", "supergroup"])
)
async def handle_request_text(message: Message, state: FSMContext):
    """
    Handle text messages when user is in waiting_for_problem state
    PROPER FSM handler - only triggers when user is in this state
    """
    user_id = message.from_user.id
    chat_id = message.chat.id

    bot_logger.info(f"📨 REQUEST TEXT received from user {user_id} in chat {chat_id}")

    # Check timeout (10 minutes)
    state_data = await state.get_data()
    request_started_at = state_data.get('request_started_at')

    if request_started_at:
        from datetime import datetime
        elapsed_minutes = (datetime.now().timestamp() - request_started_at) / 60
        if elapsed_minutes > 10:
            await message.reply(
                "⏱️ Время ожидания истекло (10 минут).\n\n"
                "Используйте /request чтобы создать новую заявку.",
                parse_mode="Markdown"
            )
            await state.clear()
            bot_logger.info(f"⏱️ Request timeout for user {user_id}, state cleared")
            return

    problem_text = message.text.strip()

    if len(problem_text) < 5:
        await message.reply(
            "❌ Описание слишком короткое (минимум 5 символов).\n\n"
            "Опишите проблему подробнее.",
            parse_mode="Markdown"
        )
        return

    # Get state data
    state_data = await state.get_data()

    # Auto-create request with context
    async for session in get_async_session():
        try:
            mapping = await support_requests_service.get_chat_mapping(session, chat_id)

            if not mapping:
                await message.reply("❌ Чат не настроен для заявок.")
                await state.clear()
                return

            # Get user info
            user = message.from_user
            username = user.username or user.full_name or "Unknown"

            # Auto-generate title from first 50 chars
            title = problem_text[:50] + ("..." if len(problem_text) > 50 else "")

            # Description now contains ONLY the problem text
            # User context will be added as a comment after task creation
            description = problem_text

            bot_logger.info(f"🔄 Creating auto-request: title='{title[:30]}'")

            # Create in database
            request = await support_requests_service.create_support_request(
                session=session,
                chat_id=chat_id,
                user_id=user_id,
                user_name=username,
                title=title,
                description=description,
                priority="medium"
            )

            bot_logger.info(f"✅ Created support request #{request.id} in database")

            # Submit to Plane
            success, error_msg, plane_request = await support_requests_service.submit_to_plane(
                session, request.id
            )

            if success and plane_request:
                bot_logger.info(f"✅ Request #{request.id} submitted to Plane successfully")

                # Build Plane link
                plane_url = f"https://plane.hhivp.com/hhivp/projects/{plane_request.plane_project_id}/issues/{plane_request.plane_issue_id}"

                # Add user context as a comment to the Plane issue
                user_context_comment = (
                    f"**📱 Telegram User Info:**\n"
                    f"- **Full Name:** {user.full_name}\n"
                    f"- **Username:** @{user.username or 'не указан'}\n"
                    f"- **User ID:** `{user.id}`\n"
                    f"- **Chat:** {message.chat.title}\n"
                    f"- **Time:** {datetime.now().strftime('%d.%m.%Y %H:%M')}"
                )

                try:
                    from ...integrations.plane import plane_api
                    comment_result = await plane_api.create_issue_comment(
                        project_id=plane_request.plane_project_id,
                        issue_id=plane_request.plane_issue_id,
                        comment=user_context_comment
                    )
                    if comment_result:
                        bot_logger.info(f"✅ Added user context comment to issue {plane_request.plane_issue_id}")
                    else:
                        bot_logger.warning(f"⚠️ Failed to add comment to issue {plane_request.plane_issue_id}")
                except Exception as e:
                    bot_logger.error(f"Error adding comment to Plane issue: {e}")

                # Reply to user - ONLY ticket number (no link for clients)
                await message.reply(
                    f"✅ **Заявка создана!**\n\n"
                    f"📋 Номер заявки: **#{plane_request.plane_sequence_id}**\n"
                    f"📁 Проект: {mapping.plane_project_name}\n\n"
                    f"Ваша заявка принята и отправлена в обработку.\n"
                    f"Администраторы уведомлены.",
                    parse_mode="Markdown"
                )

                # Notify all admins in private messages
                from ...config import settings
                user_info = (
                    f"👤 **От кого:** {message.from_user.full_name}\n"
                    f"🆔 **Telegram ID:** `{message.from_user.id}`\n"
                    f"👤 **Username:** @{message.from_user.username or 'не указан'}\n"
                    f"💬 **Чат:** {message.chat.title}\n"
                )

                admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔗 Открыть в Plane", url=plane_url)]
                ])

                for admin_id in settings.admin_user_id_list:
                    try:
                        await message.bot.send_message(
                            chat_id=admin_id,
                            text=(
                                f"🔔 **Новая заявка #{plane_request.plane_sequence_id}**\n\n"
                                f"{user_info}\n"
                                f"📝 **Проблема:**\n{problem_text[:500]}\n\n"
                                f"📁 **Проект:** {mapping.plane_project_name}"
                            ),
                            reply_markup=admin_keyboard,
                            parse_mode="Markdown"
                        )
                        bot_logger.info(f"✅ Notified admin {admin_id} about request #{plane_request.plane_sequence_id}")
                    except Exception as e:
                        bot_logger.warning(f"Failed to notify admin {admin_id}: {e}")
            else:
                bot_logger.error(f"Failed to submit request #{request.id} to Plane: {error_msg}")
                await message.reply(
                    f"⚠️ Заявка создана локально\n\n"
                    f"📋 Номер: {request.id}\n\n"
                    f"Но не удалось отправить в Plane.\n"
                    f"Ошибка: {error_msg}",
                    parse_mode=None
                )

            # IMPORTANT: Clear FSM state after successful processing
            await state.clear()
            bot_logger.info(f"🧹 FSM state cleared for user {user_id}")

        except Exception as e:
            bot_logger.error(f"Error creating request: {e}")
            await message.reply(
                "❌ Произошла ошибка при создании заявки.\n\n"
                "Попробуйте ещё раз или обратитесь к администратору.",
                parse_mode=None
            )
            # Clear state even on error
            await state.clear()


@router.message(Command("task"))
async def cmd_task(message: Message):
    """
    Create task from any message via reply

    Usage in group:
    1. Reply to any message with /task
    2. Optionally add text: /task дополнительный комментарий

    Bot creates task in Plane:
    - Description: text from replied message
    - Title: auto-generated from first 50 chars
    - Priority: medium
    - Comment with original author info + link
    """
    chat_id = message.chat.id

    bot_logger.info(f"🎯 TASK command: user={message.from_user.id}, chat={chat_id}")

    # Check if group chat
    if chat_id > 0:
        await message.reply(
            "❌ Эта команда работает только в групповых чатах.\n\n"
            "Используйте её в чате вашей команды для создания задачи.",
            parse_mode="Markdown"
        )
        return

    # Check if this is a reply to another message
    if not message.reply_to_message:
        await message.reply(
            "❌ Эта команда работает только в ответ (reply) на сообщение.\n\n"
            "**Как использовать:**\n"
            "1. Найдите сообщение, из которого хотите создать задачу\n"
            "2. Нажмите Reply на это сообщение\n"
            "3. Напишите `/task` (можно добавить комментарий)\n\n"
            "**Примеры:**\n"
            "`/task` - создать задачу из текста сообщения\n"
            "`/task срочно!` - создать задачу + добавить комментарий",
            parse_mode="Markdown"
        )
        return

    # Get text from replied message
    replied_message = message.reply_to_message
    problem_text = replied_message.text or replied_message.caption

    if not problem_text:
        await message.reply(
            "❌ Исходное сообщение не содержит текста.\n\n"
            "Команда /task работает только с текстовыми сообщениями.",
            parse_mode="Markdown"
        )
        return

    if len(problem_text) < 5:
        await message.reply(
            "❌ Текст слишком короткий (минимум 5 символов).\n\n"
            "Невозможно создать задачу из такого короткого описания.",
            parse_mode="Markdown"
        )
        return

    # Check if chat is configured
    async for session in get_async_session():
        try:
            mapping = await support_requests_service.get_chat_mapping(session, chat_id)

            if not mapping:
                await message.reply(
                    "❌ Этот чат не настроен для заявок.\n\n"
                    "Обратитесь к администратору для настройки (/setup_chat).",
                    parse_mode="Markdown"
                )
                return

            # Get author of original message
            original_author = replied_message.from_user
            original_author_name = original_author.full_name
            original_author_username = f"@{original_author.username}" if original_author.username else "не указан"

            # Get creator (who used /task command)
            creator = message.from_user
            creator_name = creator.username or creator.full_name or "Unknown"

            # Auto-generate title from first 50 chars
            title = problem_text[:50] + ("..." if len(problem_text) > 50 else "")

            # Description is the problem text
            description = problem_text

            bot_logger.info(f"🔄 Creating task from reply: title='{title[:30]}'")

            # Create in database
            request = await support_requests_service.create_support_request(
                session=session,
                chat_id=chat_id,
                user_id=original_author.id,  # Original author as request owner
                user_name=original_author_name,
                title=title,
                description=description,
                priority="medium"
            )

            bot_logger.info(f"✅ Created support request #{request.id} in database")

            # Submit to Plane
            success, error_msg, plane_request = await support_requests_service.submit_to_plane(
                session, request.id
            )

            if success and plane_request:
                bot_logger.info(f"✅ Request #{request.id} submitted to Plane successfully")

                # Build Plane link
                plane_url = f"https://plane.hhivp.com/hhivp/projects/{plane_request.plane_project_id}/issues/{plane_request.plane_issue_id}"

                # Build message link
                # For private groups: t.me/c/{chat_id without -100}/{message_id}
                # For public groups with username: t.me/{username}/{message_id}
                message_link = None
                chat_username = message.chat.username
                if chat_username:
                    # Public channel/group
                    message_link = f"https://t.me/{chat_username}/{replied_message.message_id}"
                elif chat_id < 0:
                    # Private group/supergroup
                    # Remove -100 prefix from chat_id for link
                    chat_id_str = str(chat_id)
                    if chat_id_str.startswith("-100"):
                        clean_chat_id = chat_id_str[4:]
                        message_link = f"https://t.me/c/{clean_chat_id}/{replied_message.message_id}"

                # Get additional comment from command (if any)
                command_parts = message.text.split(maxsplit=1)
                additional_comment = command_parts[1] if len(command_parts) > 1 else None

                # Add context comment to Plane issue
                context_lines = [
                    "**📱 Контекст задачи:**",
                    f"- **Автор сообщения:** {original_author_name}",
                    f"- **Username:** {original_author_username}",
                    f"- **User ID:** `{original_author.id}`",
                    f"- **Чат:** {message.chat.title}",
                    f"- **Создал задачу:** @{creator.username or creator.full_name}",
                    f"- **Время:** {datetime.now().strftime('%d.%m.%Y %H:%M')}"
                ]

                if message_link:
                    context_lines.append(f"- **Ссылка на сообщение:** {message_link}")

                if additional_comment:
                    context_lines.append(f"\n**💬 Дополнительно от создателя:**\n{additional_comment}")

                context_comment = "\n".join(context_lines)

                try:
                    from ...integrations.plane import plane_api
                    comment_result = await plane_api.create_issue_comment(
                        project_id=plane_request.plane_project_id,
                        issue_id=plane_request.plane_issue_id,
                        comment=context_comment
                    )
                    if comment_result:
                        bot_logger.info(f"✅ Added context comment to issue {plane_request.plane_issue_id}")
                    else:
                        bot_logger.warning(f"⚠️ Failed to add comment to issue {plane_request.plane_issue_id}")
                except Exception as e:
                    bot_logger.error(f"Error adding comment to Plane issue: {e}")

                # Reply to command message
                reply_text = (
                    f"✅ **Задача создана из сообщения!**\n\n"
                    f"📋 Номер задачи: **#{plane_request.plane_sequence_id}**\n"
                    f"📁 Проект: {mapping.plane_project_name}\n"
                    f"👤 Автор сообщения: {original_author_name}\n\n"
                    f"Задача отправлена в обработку.\n"
                    f"Администраторы уведомлены."
                )

                await message.reply(reply_text, parse_mode="Markdown")

                # Notify all admins in private messages
                admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔗 Открыть в Plane", url=plane_url)]
                ])

                admin_info = (
                    f"👤 **Автор сообщения:** {original_author_name}\n"
                    f"🆔 **Telegram ID:** `{original_author.id}`\n"
                    f"👤 **Username:** {original_author_username}\n"
                    f"💬 **Чат:** {message.chat.title}\n"
                    f"🎯 **Создал задачу:** @{creator.username or creator.full_name}\n"
                )

                if message_link:
                    admin_info += f"🔗 **Ссылка:** {message_link}\n"

                for admin_id in settings.admin_user_id_list:
                    try:
                        admin_text = (
                            f"🎯 **Новая задача #{plane_request.plane_sequence_id}** (из /task)\n\n"
                            f"{admin_info}\n"
                            f"📝 **Описание:**\n{problem_text[:500]}\n\n"
                            f"📁 **Проект:** {mapping.plane_project_name}"
                        )

                        if additional_comment:
                            admin_text += f"\n\n💬 **Комментарий:** {additional_comment}"

                        await message.bot.send_message(
                            chat_id=admin_id,
                            text=admin_text,
                            reply_markup=admin_keyboard,
                            parse_mode="Markdown"
                        )
                        bot_logger.info(f"✅ Notified admin {admin_id} about task #{plane_request.plane_sequence_id}")
                    except Exception as e:
                        bot_logger.warning(f"Failed to notify admin {admin_id}: {e}")
            else:
                bot_logger.error(f"Failed to submit request #{request.id} to Plane: {error_msg}")
                await message.reply(
                    f"⚠️ Задача создана локально\n\n"
                    f"📋 Номер: {request.id}\n\n"
                    f"Но не удалось отправить в Plane.\n"
                    f"Ошибка: {error_msg}",
                    parse_mode=None
                )

        except Exception as e:
            bot_logger.error(f"Error creating task: {e}")
            await message.reply(
                "❌ Произошла ошибка при создании задачи.\n\n"
                "Попробуйте ещё раз или обратитесь к администратору.",
                parse_mode=None
            )
