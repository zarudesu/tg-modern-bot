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

    # Set FSM state - PROPER aiogram 3 way
    await state.set_state(SupportRequestStates.waiting_for_problem)

    # Store mapping info in state data
    await state.update_data(
        chat_id=chat_id,
        project_name=mapping.plane_project_name
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

            # Create description with context
            description = (
                f"**Заявка от:** @{username}\n"
                f"**Чат:** {message.chat.title}\n"
                f"**Время:** {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                f"**Проблема:**\n{problem_text}"
            )

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

                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔗 Открыть в Plane", url=plane_url)],
                    [InlineKeyboardButton(text="📋 Мои заявки", callback_data="my_requests")]
                ])

                await message.reply(
                    f"✅ **Заявка создана!**\n\n"
                    f"📋 Номер в боте: #{request.id}\n"
                    f"🔢 Номер в Plane: #{plane_request.plane_sequence_id}\n"
                    f"📝 Название: {title}\n"
                    f"📁 Проект: {mapping.plane_project_name}\n"
                    f"⚡ Приоритет: Средний\n\n"
                    f"Заявка отправлена в Plane для обработки.",
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
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
