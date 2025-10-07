"""
Support Requests Handlers - Command and FSM handlers
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from .states import SupportRequestStates
from ...database.database import get_async_session
from ...services.support_requests_service import support_requests_service
from ...utils.logger import bot_logger
from ...config import settings


router = Router()


def escape_markdown_v2(text: str) -> str:
    """Escape special characters for MarkdownV2"""
    chars_to_escape = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!', '@']
    for char in chars_to_escape:
        text = text.replace(char, f'\\{char}')
    return text


@router.message(Command("new_request"))
async def cmd_new_request(message: Message, state: FSMContext):
    """
    Start creating a new support request
    Works in both private and group chats
    """
    user_id = message.from_user.id
    chat_id = message.chat.id

    bot_logger.error(f"🔥🔥🔥 NEW_REQUEST HANDLER CALLED! User {user_id} chat {chat_id} 🔥🔥🔥")
    bot_logger.info(f"User {user_id} started new request from chat {chat_id}")

    # Check if this is a group chat with mapping
    if chat_id < 0:  # Group chat
        async for session in get_async_session():
            mapping = await support_requests_service.get_chat_mapping(session, chat_id)
        if not mapping:
            await message.reply(
                "❌ *Этот чат не настроен для заявок*\n\n"
                "Обратитесь к администратору для настройки\\.",
                parse_mode="MarkdownV2"
            )
            return

        # Store chat info in FSM
        await state.update_data(
            chat_id=chat_id,
            chat_title=message.chat.title or "Unknown",
            project_id=mapping.plane_project_id,
            project_name=mapping.plane_project_name
        )

        # Start request creation directly in chat
        project_escaped = escape_markdown_v2(mapping.plane_project_name)
        await message.reply(
            f"📝 *Создание заявки*\n\n"
            f"📁 Проект: {project_escaped}\n\n"
            f"*Шаг 1/3: Название заявки*\n\n"
            f"Напишите краткое название проблемы \\(минимум 5 символов\\)",
            parse_mode="MarkdownV2"
        )

        # Set state to wait for title
        await state.set_state(SupportRequestStates.waiting_for_title)

    else:  # Private chat
        await message.reply(
            "ℹ️ *Как создать заявку:*\n\n"
            "1\\. Перейдите в групповой чат вашей организации\n"
            "2\\. Напишите команду `/new_request`\n"
            "3\\. Следуйте инструкциям\n\n"
            "_Заявки создаются только из настроенных групповых чатов\\._",
            parse_mode="MarkdownV2"
        )


@router.message(F.text, SupportRequestStates.waiting_for_title)
async def process_request_title(message: Message, state: FSMContext):
    """Process request title"""
    title = message.text.strip()

    if len(title) < 5:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить создание заявки", callback_data="cancel_request")]
        ])
        await message.reply(
            "❌ *Название слишком короткое*\n\n"
            "Минимум 5 символов\\. Попробуйте ещё раз\\.",
            reply_markup=keyboard,
            parse_mode="MarkdownV2"
        )
        return

    if len(title) > 200:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить создание заявки", callback_data="cancel_request")]
        ])
        await message.reply(
            "❌ *Название слишком длинное*\n\n"
            "Максимум 200 символов\\. Попробуйте ещё раз\\.",
            reply_markup=keyboard,
            parse_mode="MarkdownV2"
        )
        return

    # Save title and ask for description
    await state.update_data(title=title)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭️ Пропустить описание", callback_data="skip_description")],
        [InlineKeyboardButton(text="❌ Отменить создание", callback_data="cancel_request")]
    ])

    title_escaped = escape_markdown_v2(title)
    await message.reply(
        f"✅ *Название принято*\n\n"
        f"📝 _{title_escaped}_\n\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"📋 *Шаг 2/3: Описание проблемы*\n\n"
        f"Опишите проблему подробнее\\. Чем детальнее описание, тем быстрее решим\\.\n\n"
        f"💡 Можете пропустить этот шаг\\.",
        reply_markup=keyboard,
        parse_mode="MarkdownV2"
    )

    await state.set_state(SupportRequestStates.waiting_for_description)


@router.message(F.text, SupportRequestStates.waiting_for_description)
async def process_request_description(message: Message, state: FSMContext):
    """Process request description"""
    description = message.text.strip()

    if len(description) > 2000:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭️ Пропустить описание", callback_data="skip_description")],
            [InlineKeyboardButton(text="❌ Отменить создание", callback_data="cancel_request")]
        ])
        await message.reply(
            "❌ *Описание слишком длинное*\n\n"
            "Максимум 2000 символов\\. Попробуйте короче или пропустите\\.",
            reply_markup=keyboard,
            parse_mode="MarkdownV2"
        )
        return

    await state.update_data(description=description)

    # Show confirmation and move to priority
    desc_preview = description[:100] + "\\.\\.\\." if len(description) > 100 else description
    desc_escaped = escape_markdown_v2(desc_preview)

    data = await state.get_data()
    title_escaped = escape_markdown_v2(data.get('title', ''))

    await message.reply(
        f"✅ *Описание принято*\n\n"
        f"📝 _{desc_escaped}_\n\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"📋 *Ваша заявка:*\n"
        f"• Название: {title_escaped}\n"
        f"• Описание: есть\n\n"
        f"Переходим к последнему шагу\\.\\.\\.",
        parse_mode="MarkdownV2"
    )

    await show_priority_selection(message, state)


@router.callback_query(F.data == "skip_description")
async def skip_description(callback: CallbackQuery, state: FSMContext):
    """Skip description step"""
    await state.update_data(description=None)

    data = await state.get_data()
    title_escaped = escape_markdown_v2(data.get('title', ''))

    await callback.message.answer(
        f"⏭️ *Описание пропущено*\n\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"📋 *Ваша заявка:*\n"
        f"• Название: {title_escaped}\n"
        f"• Описание: нет\n\n"
        f"Переходим к последнему шагу\\.\\.\\.",
        parse_mode="MarkdownV2"
    )

    await callback.answer()
    await show_priority_selection(callback.message, state)


async def show_priority_selection(message: Message, state: FSMContext):
    """Show priority selection keyboard"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔴 Срочно", callback_data="priority_urgent"),
            InlineKeyboardButton(text="🟠 Высокий", callback_data="priority_high")
        ],
        [
            InlineKeyboardButton(text="🟡 Средний", callback_data="priority_medium"),
            InlineKeyboardButton(text="🟢 Низкий", callback_data="priority_low")
        ],
        [InlineKeyboardButton(text="❌ Отменить создание", callback_data="cancel_request")]
    ])

    await message.answer(
        "⚡ *Шаг 3/3: Приоритет заявки*\n\n"
        "Выберите насколько срочно нужно решить проблему:\n\n"
        "🔴 *Срочно* \\- критическая проблема, всё сломано\n"
        "🟠 *Высокий* \\- важная проблема, мешает работе\n"
        "🟡 *Средний* \\- обычная проблема\n"
        "🟢 *Низкий* \\- небольшая проблема, не горит",
        reply_markup=keyboard,
        parse_mode="MarkdownV2"
    )

    await state.set_state(SupportRequestStates.waiting_for_priority)


@router.callback_query(F.data.startswith("priority_"))
async def process_priority(callback: CallbackQuery, state: FSMContext):
    """Process priority selection and create request"""
    priority = callback.data.replace("priority_", "")

    # Get all data
    data = await state.get_data()
    title = data.get('title')
    description = data.get('description')
    chat_id = data.get('chat_id')
    project_name = data.get('project_name', 'Unknown')

    if not title or not chat_id:
        await callback.message.edit_text(
            "❌ Ошибка: неполные данные заявки\\.\n\n"
            "Попробуйте создать заявку заново\\.",
            parse_mode="MarkdownV2"
        )
        await state.clear()
        return

    # Show creating message
    title_escaped = escape_markdown_v2(title)
    priority_names = {
        'urgent': '🔴 Срочно',
        'high': '🟠 Высокий',
        'medium': '🟡 Средний',
        'low': '🟢 Низкий'
    }
    priority_text = priority_names.get(priority, priority)

    await callback.message.answer(
        f"⏳ *Создаю заявку\\.\\.\\.*\n\n"
        f"📝 {title_escaped}\n"
        f"⚡ Приоритет: {escape_markdown_v2(priority_text)}\n\n"
        f"Отправляю в Plane\\.\\.\\.",
        parse_mode="MarkdownV2"
    )
    await callback.answer()

    # Create support request in database
    async for session in get_async_session():
        try:
            user = callback.from_user
            user_name = user.full_name or user.username or f"User {user.id}"

            request = await support_requests_service.create_support_request(
                session=session,
                chat_id=chat_id,
                user_id=user.id,
                user_name=user_name,
                title=title,
                description=description,
                priority=priority
            )

            # Submit to Plane
            success, error = await support_requests_service.submit_to_plane(session, request.id)

            if success:
                # Success message
                title_escaped = escape_markdown_v2(title)
                project_escaped = escape_markdown_v2(project_name)
                priority_emoji = request.priority_emoji

                success_text = (
                    f"✅ *Заявка успешно создана\\!*\n\n"
                    f"━━━━━━━━━━━━━━━━\n\n"
                    f"📝 *Название:* {title_escaped}\n"
                    f"📁 *Проект:* {project_escaped}\n"
                    f"{priority_emoji} *Приоритет:* {escape_markdown_v2(priority.title())}\n"
                )

                if description:
                    desc_preview = description[:100] + "\\.\\.\\." if len(description) > 100 else description
                    desc_escaped = escape_markdown_v2(desc_preview)
                    success_text += f"📄 *Описание:* {desc_escaped}\n"

                success_text += f"\n━━━━━━━━━━━━━━━━\n\n"

                if request.plane_url:
                    success_text += f"🔗 [Посмотреть заявку в Plane]({escape_markdown_v2(request.plane_url)})\n\n"

                success_text += (
                    f"✉️ Администраторы получили уведомление\\.\n"
                    f"📞 Мы скоро с вами свяжемся\\!"
                )

                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📋 Мои заявки", callback_data="my_requests_list")],
                    [InlineKeyboardButton(text="➕ Создать ещё", callback_data="create_another_request")]
                ])

                await callback.message.answer(
                    success_text,
                    reply_markup=keyboard,
                    parse_mode="MarkdownV2",
                    disable_web_page_preview=True
                )

                # Send notifications to admins
                await notify_admins_about_request(callback.bot, request, user_name)

            else:
                error_escaped = escape_markdown_v2(error or "Unknown error")
                await callback.message.edit_text(
                    f"❌ *Ошибка создания заявки в Plane*\n\n"
                    f"Заявка сохранена в базе данных, но не удалось создать её в Plane\\.\n\n"
                    f"Ошибка: {error_escaped}\n\n"
                    f"_Обратитесь к администратору\\._",
                    parse_mode="MarkdownV2"
                )

            await state.clear()

        except ValueError as e:
            error_escaped = escape_markdown_v2(str(e))
            await callback.message.edit_text(
                f"❌ *Ошибка:* {error_escaped}",
                parse_mode="MarkdownV2"
            )
            await state.clear()

        except Exception as e:
            bot_logger.error(f"Error creating support request: {e}")
            await callback.message.edit_text(
                "❌ Произошла ошибка при создании заявки\\.\n\n"
                "Попробуйте позже или обратитесь к администратору\\.",
                parse_mode="MarkdownV2"
            )
            await state.clear()


@router.callback_query(F.data == "cancel_request")
async def cancel_request(callback: CallbackQuery, state: FSMContext):
    """Cancel request creation"""
    await state.clear()
    await callback.message.answer(
        "❌ *Создание заявки отменено*\n\n"
        "Если передумаете \\- просто напишите `/new_request` снова\\.",
        parse_mode="MarkdownV2"
    )
    await callback.answer()


@router.callback_query(F.data == "create_another_request")
async def create_another_request(callback: CallbackQuery, state: FSMContext):
    """Create another request - restart flow"""
    await state.clear()
    # Simulate /new_request command
    fake_message = type('FakeMessage', (), {
        'from_user': callback.from_user,
        'chat': callback.message.chat,
        'reply': callback.message.answer
    })()
    await cmd_new_request(fake_message, state)
    await callback.answer()


@router.callback_query(F.data == "my_requests_list")
async def show_my_requests(callback: CallbackQuery):
    """Show user's requests list"""
    user_id = callback.from_user.id

    async for session in get_async_session():
        requests = await support_requests_service.get_user_requests(session, user_id, limit=10)

        if not requests:
            await callback.message.answer(
                "📋 У вас пока нет заявок\\.",
                parse_mode="MarkdownV2"
            )
            await callback.answer()
            return

        text = f"📋 *Ваши заявки* \\({len(requests)}\\)\n\n"

        for i, req in enumerate(requests, 1):
            title_escaped = escape_markdown_v2(req.title[:50])
            status_emoji = req.status_emoji
            priority_emoji = req.priority_emoji

            text += f"{i}\\. {status_emoji} {priority_emoji} {title_escaped}\n"

            if req.plane_url:
                text += f"   [→ Открыть]({escape_markdown_v2(req.plane_url)})\n"

            text += "\n"

        await callback.message.answer(
            text,
            parse_mode="MarkdownV2",
            disable_web_page_preview=True
        )
        await callback.answer()


async def notify_admins_about_request(bot, request, user_name: str):
    """Notify admins about new support request"""
    title_escaped = escape_markdown_v2(request.title)
    user_escaped = escape_markdown_v2(user_name)
    project_escaped = escape_markdown_v2(request.chat_mapping.plane_project_name)
    priority_emoji = request.priority_emoji

    notification = (
        f"🔔 *Новая заявка от пользователя*\n\n"
        f"👤 *От:* {user_escaped}\n"
        f"📝 *Название:* {title_escaped}\n"
        f"📁 *Проект:* {project_escaped}\n"
        f"{priority_emoji} *Приоритет:* {escape_markdown_v2(request.priority.title())}\n\n"
    )

    if request.description:
        desc = request.description[:200]
        desc_escaped = escape_markdown_v2(desc)
        notification += f"📄 *Описание:*\n{desc_escaped}\n\n"

    if request.plane_url:
        plane_url_escaped = escape_markdown_v2(request.plane_url)
        notification += f"🔗 [Открыть в Plane]({plane_url_escaped})"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Открыть в Plane", url=request.plane_url)]
    ]) if request.plane_url else None

    # Send to all admins
    for admin_id in settings.admin_user_id_list:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=notification,
                reply_markup=keyboard,
                parse_mode="MarkdownV2",
                disable_web_page_preview=True
            )
        except Exception as e:
            bot_logger.warning(f"Failed to notify admin {admin_id}: {e}")


@router.message(Command("my_requests"))
async def cmd_my_requests(message: Message):
    """Show user's recent support requests"""
    user_id = message.from_user.id

    async for session in get_async_session():
        requests = await support_requests_service.get_user_requests(session, user_id, limit=10)

        if not requests:
            await message.reply(
                "📋 У вас пока нет заявок\\.",
                parse_mode="MarkdownV2"
            )
            return

        text = f"📋 *Ваши заявки* \\({len(requests)}\\)\n\n"

        for i, req in enumerate(requests, 1):
            title_escaped = escape_markdown_v2(req.title[:50])
            status_emoji = req.status_emoji
            priority_emoji = req.priority_emoji

            text += f"{i}\\. {status_emoji} {priority_emoji} {title_escaped}\n"

            if req.plane_url:
                text += f"   [→ Открыть]({escape_markdown_v2(req.plane_url)})\n"

            text += "\n"

        await message.reply(
            text,
            parse_mode="MarkdownV2",
            disable_web_page_preview=True
        )
