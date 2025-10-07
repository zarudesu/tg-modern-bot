"""
Support Requests Handlers - REFACTORED INLINE VERSION
All interaction via inline buttons, no FSM text handlers in groups
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

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


# Temporary storage for request data (chat_id -> request_data)
REQUEST_DATA = {}


@router.message(Command("new_request"))
async def cmd_new_request(message: Message):
    """Start creating a new support request - INLINE MODE"""
    user_id = message.from_user.id
    chat_id = message.chat.id

    bot_logger.info(f"🔥 NEW_REQUEST: user={user_id}, chat={chat_id}")

    if chat_id > 0:  # Private chat
        await message.reply(
            "ℹ️ *Создание заявок*\n\n"
            "Заявки создаются из групповых чатов\\.\n\n"
            "1\\. Перейдите в групповой чат\n"
            "2\\. Напишите `/new_request`\n"
            "3\\. Следуйте инструкциям",
            parse_mode="MarkdownV2"
        )
        return

    # Group chat
    async for session in get_async_session():
        mapping = await support_requests_service.get_chat_mapping(session, chat_id)

    if not mapping:
        await message.reply(
            "❌ *Чат не настроен*\n\n"
            "Обратитесь к администратору для настройки\\.",
            parse_mode="MarkdownV2"
        )
        return

    # Initialize request data
    request_key = f"{user_id}_{chat_id}"
    REQUEST_DATA[request_key] = {
        'user_id': user_id,
        'chat_id': chat_id,
        'project_id': mapping.plane_project_id,
        'project_name': mapping.plane_project_name,
        'user_name': message.from_user.full_name or message.from_user.username or f"User {user_id}"
    }

    bot_logger.info(f"✅ REQUEST INITIALIZED: {request_key}")

    # Step 1: Title input via inline buttons
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Ввести название", callback_data=f"req_title_{request_key}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"req_cancel_{request_key}")]
    ])

    project_escaped = escape_markdown_v2(mapping.plane_project_name)
    await message.reply(
        f"📝 *Создание заявки*\n\n"
        f"📁 Проект: {project_escaped}\n\n"
        f"*Шаг 1/3:* Нажмите кнопку ниже и отправьте сообщение с названием проблемы \\(минимум 5 символов\\)",
        reply_markup=keyboard,
        parse_mode="MarkdownV2"
    )


@router.callback_query(F.data.startswith("req_title_"))
async def start_title_input(callback: CallbackQuery):
    """Prompt for title input"""
    request_key = callback.data.replace("req_title_", "")

    bot_logger.info(f"📝 TITLE INPUT STARTED: {request_key}")

    if request_key not in REQUEST_DATA:
        await callback.answer("❌ Сессия истекла, начните заново", show_alert=True)
        return

    # Mark that we're waiting for title
    REQUEST_DATA[request_key]['waiting_for'] = 'title'

    await callback.message.edit_text(
        "📝 *Введите название заявки*\n\n"
        "Напишите следующим сообщением краткое описание проблемы \\(минимум 5 символов\\)\n\n"
        "_Ожидаю ваше сообщение\\.\\.\\._",
        parse_mode="MarkdownV2"
    )
    await callback.answer()


@router.message(F.text & F.chat.type.in_(["group", "supergroup"]))
async def handle_group_text(message: Message):
    """Handle text messages in group - check if waiting for input"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    request_key = f"{user_id}_{chat_id}"

    if request_key not in REQUEST_DATA:
        return  # Not our request

    waiting_for = REQUEST_DATA[request_key].get('waiting_for')

    bot_logger.info(f"📨 GROUP TEXT: key={request_key}, waiting_for={waiting_for}, text={message.text[:50]}")

    if waiting_for == 'title':
        await process_title(message, request_key)
    elif waiting_for == 'description':
        await process_description(message, request_key)


async def process_title(message: Message, request_key: str):
    """Process title input"""
    title = message.text.strip()

    bot_logger.info(f"✍️ PROCESSING TITLE: key={request_key}, title={title}")

    if len(title) < 5:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"req_title_{request_key}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"req_cancel_{request_key}")]
        ])
        await message.reply(
            "❌ *Слишком короткое название*\n\n"
            "Минимум 5 символов\\. Попробуйте ещё раз\\.",
            reply_markup=keyboard,
            parse_mode="MarkdownV2"
        )
        return

    if len(title) > 200:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"req_title_{request_key}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"req_cancel_{request_key}")]
        ])
        await message.reply(
            "❌ *Слишком длинное название*\n\n"
            "Максимум 200 символов\\.",
            reply_markup=keyboard,
            parse_mode="MarkdownV2"
        )
        return

    # Save title
    REQUEST_DATA[request_key]['title'] = title
    REQUEST_DATA[request_key]['waiting_for'] = None

    bot_logger.info(f"✅ TITLE SAVED: key={request_key}")

    # Move to description
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Добавить описание", callback_data=f"req_desc_{request_key}")],
        [InlineKeyboardButton(text="⏭️ Пропустить", callback_data=f"req_skip_desc_{request_key}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"req_cancel_{request_key}")]
    ])

    title_escaped = escape_markdown_v2(title)
    await message.reply(
        f"✅ *Название принято*\n\n"
        f"📝 _{title_escaped}_\n\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"*Шаг 2/3:* Хотите добавить описание?",
        reply_markup=keyboard,
        parse_mode="MarkdownV2"
    )


@router.callback_query(F.data.startswith("req_desc_"))
async def start_description_input(callback: CallbackQuery):
    """Start description input"""
    request_key = callback.data.replace("req_desc_", "")

    bot_logger.info(f"📝 DESCRIPTION INPUT STARTED: {request_key}")

    if request_key not in REQUEST_DATA:
        await callback.answer("❌ Сессия истекла", show_alert=True)
        return

    REQUEST_DATA[request_key]['waiting_for'] = 'description'

    await callback.message.edit_text(
        "📝 *Опишите проблему подробнее*\n\n"
        "Напишите следующим сообщением детали проблемы\\.\n\n"
        "_Ожидаю ваше сообщение\\.\\.\\._",
        parse_mode="MarkdownV2"
    )
    await callback.answer()


async def process_description(message: Message, request_key: str):
    """Process description input"""
    description = message.text.strip()

    bot_logger.info(f"✍️ PROCESSING DESCRIPTION: key={request_key}")

    if len(description) > 2000:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"req_desc_{request_key}")],
            [InlineKeyboardButton(text="⏭️ Пропустить", callback_data=f"req_skip_desc_{request_key}")]
        ])
        await message.reply(
            "❌ *Слишком длинное описание*\n\n"
            "Максимум 2000 символов\\.",
            reply_markup=keyboard,
            parse_mode="MarkdownV2"
        )
        return

    REQUEST_DATA[request_key]['description'] = description
    REQUEST_DATA[request_key]['waiting_for'] = None

    bot_logger.info(f"✅ DESCRIPTION SAVED: key={request_key}")

    await show_priority_selection(message, request_key)


@router.callback_query(F.data.startswith("req_skip_desc_"))
async def skip_description(callback: CallbackQuery):
    """Skip description"""
    request_key = callback.data.replace("req_skip_desc_", "")

    bot_logger.info(f"⏭️ DESCRIPTION SKIPPED: {request_key}")

    if request_key not in REQUEST_DATA:
        await callback.answer("❌ Сессия истекла", show_alert=True)
        return

    REQUEST_DATA[request_key]['description'] = None
    REQUEST_DATA[request_key]['waiting_for'] = None

    await callback.message.edit_text(
        "⏭️ *Описание пропущено*\n\n"
        "Переходим к выбору приоритета\\.\\.\\.",
        parse_mode="MarkdownV2"
    )
    await callback.answer()

    await show_priority_selection(callback.message, request_key)


async def show_priority_selection(message: Message, request_key: str):
    """Show priority selection"""
    bot_logger.info(f"⚡ SHOWING PRIORITY: key={request_key}")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔴 Срочно", callback_data=f"req_pri_urgent_{request_key}"),
            InlineKeyboardButton(text="🟠 Высокий", callback_data=f"req_pri_high_{request_key}")
        ],
        [
            InlineKeyboardButton(text="🟡 Средний", callback_data=f"req_pri_medium_{request_key}"),
            InlineKeyboardButton(text="🟢 Низкий", callback_data=f"req_pri_low_{request_key}")
        ]
    ])

    await message.answer(
        "⚡ *Шаг 3/3: Приоритет*\n\n"
        "Насколько срочно нужно решить проблему?\n\n"
        "🔴 *Срочно* \\- критично, всё сломано\n"
        "🟠 *Высокий* \\- важно, мешает работе\n"
        "🟡 *Средний* \\- обычная проблема\n"
        "🟢 *Низкий* \\- не срочно",
        reply_markup=keyboard,
        parse_mode="MarkdownV2"
    )


@router.callback_query(F.data.startswith("req_pri_"))
async def process_priority(callback: CallbackQuery):
    """Process priority and create request"""
    parts = callback.data.split("_", 3)
    priority = parts[2]  # urgent, high, medium, low
    request_key = parts[3]

    bot_logger.info(f"⚡ PRIORITY SELECTED: key={request_key}, priority={priority}")

    if request_key not in REQUEST_DATA:
        await callback.answer("❌ Сессия истекла", show_alert=True)
        return

    data = REQUEST_DATA[request_key]

    # Create request
    await callback.message.answer(
        f"⏳ *Создаю заявку\\.\\.\\.*\n\n"
        f"Отправляю в Plane\\.\\.\\.",
        parse_mode="MarkdownV2"
    )
    await callback.answer()

    async for session in get_async_session():
        try:
            request = await support_requests_service.create_support_request(
                session=session,
                chat_id=data['chat_id'],
                user_id=data['user_id'],
                user_name=data['user_name'],
                title=data['title'],
                description=data.get('description'),
                priority=priority
            )

            bot_logger.info(f"✅ REQUEST CREATED: id={request.id}")

            # Submit to Plane
            success, error = await support_requests_service.submit_to_plane(session, request.id)

            if success:
                title_escaped = escape_markdown_v2(data['title'])
                project_escaped = escape_markdown_v2(data['project_name'])

                success_text = (
                    f"✅ *Заявка создана\\!*\n\n"
                    f"━━━━━━━━━━━━━━━━\n\n"
                    f"📝 {title_escaped}\n"
                    f"📁 {project_escaped}\n\n"
                    f"✉️ Администраторы уведомлены\\.\n"
                    f"📞 Скоро свяжемся с вами\\!"
                )

                if request.plane_url:
                    success_text += f"\n\n🔗 [Посмотреть в Plane]({escape_markdown_v2(request.plane_url)})"

                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Создать ещё заявку", callback_data=f"req_new_{data['chat_id']}")]
                ])

                await callback.message.answer(
                    success_text,
                    reply_markup=keyboard,
                    parse_mode="MarkdownV2",
                    disable_web_page_preview=True
                )

                bot_logger.info(f"🎉 REQUEST COMPLETED: id={request.id}")

                # Notify admins
                await notify_admins(callback.bot, request, data['user_name'])

            else:
                await callback.message.answer(
                    f"❌ *Ошибка создания в Plane*\n\n"
                    f"{escape_markdown_v2(error or 'Unknown error')}",
                    parse_mode="MarkdownV2"
                )

        except Exception as e:
            bot_logger.error(f"💥 REQUEST ERROR: {e}")
            await callback.message.answer(
                "❌ *Произошла ошибка*\n\n"
                "Попробуйте позже\\.",
                parse_mode="MarkdownV2"
            )

    # Cleanup
    if request_key in REQUEST_DATA:
        del REQUEST_DATA[request_key]


@router.callback_query(F.data.startswith("req_cancel_"))
async def cancel_request(callback: CallbackQuery):
    """Cancel request creation"""
    request_key = callback.data.replace("req_cancel_", "")

    bot_logger.info(f"❌ REQUEST CANCELLED: {request_key}")

    if request_key in REQUEST_DATA:
        del REQUEST_DATA[request_key]

    await callback.message.edit_text(
        "❌ *Создание отменено*\n\n"
        "Напишите `/new_request` чтобы начать заново\\.",
        parse_mode="MarkdownV2"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("req_new_"))
async def create_new_request(callback: CallbackQuery):
    """Start new request from button"""
    chat_id = int(callback.data.replace("req_new_", ""))

    # Simulate /new_request command
    fake_message = type('FakeMessage', (), {
        'from_user': callback.from_user,
        'chat': type('Chat', (), {'id': chat_id, 'type': 'supergroup'})(),
        'reply': callback.message.answer
    })()

    await cmd_new_request(fake_message)
    await callback.answer()


async def notify_admins(bot, request, user_name: str):
    """Notify admins about new request"""
    title_escaped = escape_markdown_v2(request.title)
    user_escaped = escape_markdown_v2(user_name)

    notification = (
        f"🔔 *Новая заявка*\n\n"
        f"👤 От: {user_escaped}\n"
        f"📝 {title_escaped}\n\n"
    )

    if request.plane_url:
        notification += f"🔗 [Открыть в Plane]({escape_markdown_v2(request.plane_url)})"

    for admin_id in settings.admin_user_id_list:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=notification,
                parse_mode="MarkdownV2",
                disable_web_page_preview=True
            )
        except Exception as e:
            bot_logger.warning(f"Failed to notify admin {admin_id}: {e}")


@router.message(Command("my_requests"))
async def cmd_my_requests(message: Message):
    """Show user's requests"""
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
            text += f"{i}\\. {req.status_emoji} {req.priority_emoji} {title_escaped}\n"

            if req.plane_url:
                text += f"   [→ Открыть]({escape_markdown_v2(req.plane_url)})\n"

            text += "\n"

        await message.reply(
            text,
            parse_mode="MarkdownV2",
            disable_web_page_preview=True
        )
