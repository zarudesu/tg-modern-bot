"""
Voice Message Transcription Handler

Два режима работы:

1. ЛОКАЛЬНАЯ ТРАНСКРИПЦИЯ (если n8n не настроен):
   - Whisper API → текст
   - Показывает кнопки для действий

2. AI VOICE REPORT (если n8n настроен):
   - Отправляет в n8n → Whisper + AI анализ
   - AI ищет задачу в Plane
   - Автоматически создаёт отчёт
"""

import os
import tempfile
import aiohttp
from typing import Optional

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from ..config import settings
from ..utils.logger import bot_logger
from ..services.n8n_ai_service import n8n_ai_service


router = Router(name="voice_transcription")

# Store transcriptions temporarily for task creation
_transcription_cache: dict = {}  # message_id -> transcription


async def download_voice_file(bot: Bot, file_id: str) -> Optional[str]:
    """
    Download voice file from Telegram and save to temp file.

    Returns path to temp file or None on error.
    """
    try:
        # Get file info from Telegram
        file = await bot.get_file(file_id)
        file_path = file.file_path

        if not file_path:
            bot_logger.error("Voice file has no file_path")
            return None

        # Download file
        file_url = f"https://api.telegram.org/file/bot{settings.telegram_token}/{file_path}"

        async with aiohttp.ClientSession() as session:
            async with session.get(file_url) as resp:
                if resp.status != 200:
                    bot_logger.error(f"Failed to download voice file: HTTP {resp.status}")
                    return None

                # Save to temp file (Whisper accepts ogg, mp3, wav, etc.)
                suffix = ".ogg" if file_path.endswith(".oga") else os.path.splitext(file_path)[1]
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(await resp.read())
                    return tmp.name

    except Exception as e:
        bot_logger.error(f"Error downloading voice file: {e}")
        return None


async def get_voice_file_url(bot: Bot, file_id: str) -> Optional[str]:
    """
    Get direct URL to voice file (for n8n to download).

    Returns URL or None on error.
    """
    try:
        file = await bot.get_file(file_id)
        file_path = file.file_path

        if not file_path:
            return None

        return f"https://api.telegram.org/file/bot{settings.telegram_token}/{file_path}"

    except Exception as e:
        bot_logger.error(f"Error getting voice file URL: {e}")
        return None


async def transcribe_with_whisper(file_path: str) -> Optional[str]:
    """
    Transcribe audio file using Whisper API.

    Supports multiple providers:
    1. Groq (free, fast) - GROQ_API_KEY
    2. OpenAI (paid) - OPENAI_API_KEY

    Returns transcription text or None on error.
    """
    # Try Groq first (free), then OpenAI
    groq_key = getattr(settings, 'groq_api_key', None)
    openai_key = getattr(settings, 'openai_api_key', None)

    if groq_key:
        # Use Groq (free, fast)
        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        api_key = groq_key
        model = "whisper-large-v3-turbo"  # Fast & cheap
        bot_logger.info("Using Groq Whisper for transcription")
    elif openai_key:
        # Fallback to OpenAI
        url = "https://api.openai.com/v1/audio/transcriptions"
        api_key = openai_key
        model = "whisper-1"
        bot_logger.info("Using OpenAI Whisper for transcription")
    else:
        bot_logger.warning("No Whisper API key configured (GROQ_API_KEY or OPENAI_API_KEY)")
        return None

    try:
        headers = {
            "Authorization": f"Bearer {api_key}"
        }

        async with aiohttp.ClientSession() as session:
            with open(file_path, "rb") as audio_file:
                form = aiohttp.FormData()
                form.add_field("file", audio_file, filename="voice.ogg")
                form.add_field("model", model)
                form.add_field("language", "ru")  # Russian by default
                form.add_field("response_format", "text")

                async with session.post(url, headers=headers, data=form) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        bot_logger.error(f"Whisper API error: {resp.status} - {error_text}")
                        return None

                    transcription = await resp.text()
                    return transcription.strip()

    except Exception as e:
        bot_logger.error(f"Error transcribing with Whisper: {e}")
        return None
    finally:
        # Clean up temp file
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
        except Exception as e:
            bot_logger.warning(f"Failed to delete temp file: {e}")


def create_transcription_keyboard(message_id: int, chat_id: int) -> InlineKeyboardMarkup:
    """Create keyboard with options for what to do with transcription"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📝 Создать задачу",
                callback_data=f"voice_task:{chat_id}:{message_id}"
            ),
            InlineKeyboardButton(
                text="📋 В журнал работ",
                callback_data=f"voice_journal:{chat_id}:{message_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="📧 Отправить email-задачу",
                callback_data=f"voice_email:{chat_id}:{message_id}"
            )
        ]
    ])


def create_ai_report_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for AI Voice Report mode"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🤖 AI Отчёт (авто)",
                callback_data="voice_ai_report"
            )
        ],
        [
            InlineKeyboardButton(
                text="📝 Только транскрипция",
                callback_data="voice_simple_transcribe"
            )
        ]
    ])


def create_voice_result_keyboard(admin_id: int, message_id: int) -> InlineKeyboardMarkup:
    """Keyboard after AI extraction - options to use the data"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📋 Создать запись в журнале",
                callback_data=f"voice_to_journal:{admin_id}:{message_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="📝 Создать отчёт по задаче",
                callback_data=f"voice_to_report:{admin_id}:{message_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔍 Найти задачу в Plane",
                callback_data=f"voice_find_task:{admin_id}:{message_id}"
            )
        ]
    ])


@router.message(F.voice)
async def handle_voice_message(message: Message, bot: Bot):
    """
    Handle incoming voice messages.

    Режим работы зависит от настроек:
    - Если n8n настроен: AI Voice Report (полная автоматизация)
    - Если только OpenAI: локальная транскрипция
    """
    # Only process for admins (API costs money)
    if not settings.is_admin(message.from_user.id):
        # Silently ignore non-admin voice messages
        return

    # Check if ANY transcription API is configured
    has_n8n = bool(getattr(settings, 'n8n_url', None))
    has_groq = bool(getattr(settings, 'groq_api_key', None))
    has_openai = bool(getattr(settings, 'openai_api_key', None))
    has_whisper = has_groq or has_openai

    if not has_n8n and not has_whisper:
        await message.reply(
            "⚠️ Транскрипция голосовых сообщений недоступна.\n"
            "Настройте N8N_URL или OPENAI_API_KEY."
        )
        return

    # Если есть n8n - используем AI Voice Report
    if has_n8n:
        await handle_ai_voice_report(message, bot)
    else:
        # Fallback на локальную транскрипцию
        await handle_local_transcription(message, bot)


async def handle_ai_voice_report(message: Message, bot: Bot):
    """
    AI Voice Report - автоматизация через n8n.

    Workflow:
    1. Бот получает голосовое
    2. Бот транскрибирует локально через Whisper
    3. Бот отправляет транскрипцию в n8n
    4. n8n: AI extraction (длительность, дорога, исполнители, компания)
    5. n8n шлёт результат через webhook
    6. Бот показывает результат админу
    """
    status_msg = await message.reply(
        "🎤 <b>AI Voice Report</b>\n\n"
        "⏳ Обрабатываю голосовое сообщение...\n"
        "• Скачивание аудио\n"
        "• Транскрипция (Whisper)\n"
        "• AI извлечение данных",
        parse_mode="HTML"
    )

    try:
        # 1. Скачиваем и транскрибируем локально
        await status_msg.edit_text(
            "🎤 <b>AI Voice Report</b>\n\n"
            "⏳ Скачиваю голосовое...",
            parse_mode="HTML"
        )

        file_path = await download_voice_file(bot, message.voice.file_id)
        if not file_path:
            await status_msg.edit_text("❌ Не удалось скачать голосовое")
            return

        await status_msg.edit_text(
            "🎤 <b>AI Voice Report</b>\n\n"
            "⏳ Транскрибирую (Whisper)...",
            parse_mode="HTML"
        )

        transcription = await transcribe_with_whisper(file_path)
        if not transcription:
            await status_msg.edit_text(
                "❌ Не удалось транскрибировать.\n"
                "Проверьте GROQ_API_KEY или OPENAI_API_KEY в настройках."
            )
            return

        await status_msg.edit_text(
            "🎤 <b>AI Voice Report</b>\n\n"
            f"✅ Транскрипция готова ({len(transcription)} симв.)\n"
            "⏳ Отправляю на AI анализ...",
            parse_mode="HTML"
        )

        # 2. Отправляем транскрипцию в n8n для AI extraction
        success, result = await n8n_ai_service.process_voice_report(
            message=message,
            transcription=transcription,
            admin_telegram_id=message.from_user.id,
            admin_name=message.from_user.full_name
        )

        if success:
            # n8n принял запрос
            extraction = result.get('extraction', {})

            # Показываем результат сразу (n8n вернул синхронно)
            duration_h = extraction.get('duration_hours', 0)
            travel_h = extraction.get('travel_hours', 0)
            workers = extraction.get('workers', [])
            company = extraction.get('company', '?')
            description = extraction.get('description', transcription[:200])

            # Сохраняем для дальнейшей обработки
            cache_key = f"voice_report:{message.from_user.id}:{message.message_id}"
            _transcription_cache[cache_key] = {
                "transcription": transcription,
                "extraction": extraction,
                "status_message_id": status_msg.message_id,
                "chat_id": message.chat.id,
                "duration": message.voice.duration
            }

            # Формируем красивый результат
            workers_str = ", ".join(workers) if workers else "не указаны"

            await status_msg.edit_text(
                f"🎤 <b>AI Voice Report</b>\n\n"
                f"<b>📝 Транскрипция:</b>\n"
                f"<i>{transcription[:300]}{'...' if len(transcription) > 300 else ''}</i>\n\n"
                f"<b>📊 Извлечённые данные:</b>\n"
                f"⏱ Длительность: {duration_h} ч\n"
                f"🚗 Дорога: {travel_h} ч\n"
                f"👥 Исполнители: {workers_str}\n"
                f"🏢 Компания: {company}\n"
                f"📋 Описание: {description[:100]}{'...' if len(description) > 100 else ''}\n\n"
                f"<i>Используйте эти данные для создания отчёта</i>",
                parse_mode="HTML",
                reply_markup=create_voice_result_keyboard(message.from_user.id, message.message_id)
            )

            bot_logger.info(
                f"Voice transcribed and extracted via AI",
                extra={
                    "admin_id": message.from_user.id,
                    "duration": message.voice.duration,
                    "extraction": extraction
                }
            )
        else:
            # n8n недоступен - показываем только транскрипцию
            error_msg = result.get("error", "Unknown error") if result else "No response"
            bot_logger.warning(f"n8n AI extraction failed: {error_msg}")

            # Сохраняем транскрипцию
            cache_key = f"{message.chat.id}:{message.message_id}"
            _transcription_cache[cache_key] = {
                "text": transcription,
                "user_id": message.from_user.id,
                "chat_id": message.chat.id,
                "duration": message.voice.duration
            }

            await status_msg.edit_text(
                f"<b>🎤 Транскрипция</b> ({message.voice.duration}сек):\n\n"
                f"<i>{transcription}</i>\n\n"
                f"⚠️ AI анализ недоступен\n"
                f"Что сделать с этим текстом?",
                parse_mode="HTML",
                reply_markup=create_transcription_keyboard(message.message_id, message.chat.id)
            )

    except Exception as e:
        bot_logger.error(f"Error in AI voice report: {e}")
        # Use HTML to avoid markdown escaping issues
        error_text = str(e).replace("<", "&lt;").replace(">", "&gt;")
        await status_msg.edit_text(f"❌ Ошибка: {error_text}", parse_mode="HTML")


async def handle_local_transcription(message: Message, bot: Bot, status_msg: Message = None):
    """
    Локальная транскрипция через OpenAI Whisper (fallback).
    """
    if not status_msg:
        status_msg = await message.reply("🎤 Транскрибирую голосовое сообщение...")

    try:
        # 1. Download voice file
        file_path = await download_voice_file(bot, message.voice.file_id)
        if not file_path:
            await status_msg.edit_text("❌ Не удалось скачать голосовое сообщение")
            return

        # 2. Transcribe with Whisper
        transcription = await transcribe_with_whisper(file_path)
        if not transcription:
            await status_msg.edit_text("❌ Не удалось транскрибировать сообщение")
            return

        # 3. Cache transcription for later use
        cache_key = f"{message.chat.id}:{message.message_id}"
        _transcription_cache[cache_key] = {
            "text": transcription,
            "user_id": message.from_user.id,
            "chat_id": message.chat.id,
            "duration": message.voice.duration
        }

        # 4. Show transcription with action buttons
        duration_str = f"{message.voice.duration}сек"

        await status_msg.edit_text(
            f"<b>🎤 Транскрипция</b> ({duration_str}):\n\n"
            f"<i>{transcription}</i>\n\n"
            f"Что сделать с этим текстом?",
            parse_mode="HTML",
            reply_markup=create_transcription_keyboard(message.message_id, message.chat.id)
        )

        bot_logger.info(
            f"Voice transcribed for user {message.from_user.id}: "
            f"{len(transcription)} chars, {message.voice.duration}s"
        )

    except Exception as e:
        bot_logger.error(f"Error handling voice message: {e}")
        error_text = str(e).replace("<", "&lt;").replace(">", "&gt;")
        await status_msg.edit_text(f"❌ Ошибка: {error_text}", parse_mode="HTML")


@router.callback_query(F.data.startswith("voice_task:"))
async def callback_voice_to_task(callback: CallbackQuery):
    """Create Plane task from voice transcription"""
    try:
        parts = callback.data.split(":")
        chat_id = int(parts[1])
        message_id = int(parts[2])

        cache_key = f"{chat_id}:{message_id}"
        cached = _transcription_cache.get(cache_key)

        if not cached:
            await callback.answer("❌ Транскрипция истекла", show_alert=True)
            return

        transcription = cached["text"]

        # Import here to avoid circular imports
        from ..modules.chat_support.handlers import create_task_from_text

        # Try to create task
        try:
            # This would create a Plane task with transcription as description
            await callback.message.edit_text(
                f"<b>📝 Создание задачи...</b>\n\n"
                f"Текст: {transcription[:200]}{'...' if len(transcription) > 200 else ''}",
                parse_mode="HTML"
            )

            # For now, just show the text that would be used
            # Integration with /task command can be added later
            await callback.message.edit_text(
                f"<b>✅ Готово к созданию задачи</b>\n\n"
                f"Используйте команду <code>/task</code> и вставьте текст:\n\n"
                f"<i>{transcription}</i>",
                parse_mode="HTML"
            )

        except Exception as e:
            await callback.message.edit_text(f"❌ Ошибка: {e}")

        await callback.answer()

    except Exception as e:
        bot_logger.error(f"Error in voice_task callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("voice_journal:"))
async def callback_voice_to_journal(callback: CallbackQuery):
    """Add voice transcription to work journal"""
    try:
        parts = callback.data.split(":")
        chat_id = int(parts[1])
        message_id = int(parts[2])

        cache_key = f"{chat_id}:{message_id}"
        cached = _transcription_cache.get(cache_key)

        if not cached:
            await callback.answer("❌ Транскрипция истекла", show_alert=True)
            return

        transcription = cached["text"]

        await callback.message.edit_text(
            f"<b>📋 Добавить в журнал работ</b>\n\n"
            f"Текст: <i>{transcription}</i>\n\n"
            f"Используйте команду <code>/journal</code> для создания записи.",
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        bot_logger.error(f"Error in voice_journal callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("voice_email:"))
async def callback_voice_to_email(callback: CallbackQuery):
    """Create email task from voice transcription (for Daily Tasks)"""
    try:
        parts = callback.data.split(":")
        chat_id = int(parts[1])
        message_id = int(parts[2])

        cache_key = f"{chat_id}:{message_id}"
        cached = _transcription_cache.get(cache_key)

        if not cached:
            await callback.answer("❌ Транскрипция истекла", show_alert=True)
            return

        transcription = cached["text"]

        # Format as email-like task for daily_tasks processing
        email_format = f"Тема: Голосовая задача\n\n{transcription}"

        await callback.message.edit_text(
            f"<b>📧 Email-задача</b>\n\n"
            f"Отправьте следующий текст боту как обычное сообщение,\n"
            f"и он создаст задачу в Plane:\n\n"
            f"<code>{email_format}</code>",
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        bot_logger.error(f"Error in voice_email callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("voice_to_journal:"))
async def callback_voice_ai_to_journal(callback: CallbackQuery):
    """Create work journal entry from AI extraction"""
    try:
        parts = callback.data.split(":")
        admin_id = int(parts[1])
        message_id = int(parts[2])

        cache_key = f"voice_report:{admin_id}:{message_id}"
        cached = _transcription_cache.get(cache_key)

        if not cached:
            await callback.answer("❌ Данные истекли", show_alert=True)
            return

        extraction = cached.get("extraction", {})
        transcription = cached.get("transcription", "")

        # Формируем данные для журнала
        duration_h = extraction.get("duration_hours", 0)
        travel_h = extraction.get("travel_hours", 0)
        workers = extraction.get("workers", [])
        company = extraction.get("company", "")
        description = extraction.get("description", transcription[:500])

        # Показываем готовые данные
        workers_str = ", ".join(workers) if workers else "не указаны"

        await callback.message.edit_text(
            f"<b>📋 Данные для журнала работ:</b>\n\n"
            f"⏱ <b>Длительность:</b> {duration_h} ч\n"
            f"🚗 <b>Дорога:</b> {travel_h} ч\n"
            f"👥 <b>Исполнители:</b> {workers_str}\n"
            f"🏢 <b>Компания:</b> {company or 'не указана'}\n"
            f"📋 <b>Описание:</b> {description}\n\n"
            f"<i>Используйте /journal для создания записи с этими данными</i>",
            parse_mode="HTML"
        )

        await callback.answer("✅ Данные готовы")

    except Exception as e:
        bot_logger.error(f"Error in voice_to_journal callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("voice_to_report:"))
async def callback_voice_ai_to_report(callback: CallbackQuery):
    """Create task report from AI extraction"""
    try:
        parts = callback.data.split(":")
        admin_id = int(parts[1])
        message_id = int(parts[2])

        cache_key = f"voice_report:{admin_id}:{message_id}"
        cached = _transcription_cache.get(cache_key)

        if not cached:
            await callback.answer("❌ Данные истекли", show_alert=True)
            return

        extraction = cached.get("extraction", {})
        keywords = extraction.get("keywords", [])

        await callback.message.edit_text(
            f"<b>📝 Поиск задачи для отчёта</b>\n\n"
            f"Ключевые слова: {', '.join(keywords) if keywords else 'нет'}\n\n"
            f"<i>Функция в разработке.\n"
            f"Используйте веб-интерфейс Plane для создания отчёта.</i>",
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        bot_logger.error(f"Error in voice_to_report callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("voice_find_task:"))
async def callback_voice_find_task(callback: CallbackQuery):
    """Search for task in Plane based on AI extraction"""
    try:
        parts = callback.data.split(":")
        admin_id = int(parts[1])
        message_id = int(parts[2])

        cache_key = f"voice_report:{admin_id}:{message_id}"
        cached = _transcription_cache.get(cache_key)

        if not cached:
            await callback.answer("❌ Данные истекли", show_alert=True)
            return

        extraction = cached.get("extraction", {})
        keywords = extraction.get("keywords", [])
        company = extraction.get("company", "")

        await callback.message.edit_text(
            f"<b>🔍 Поиск задачи в Plane</b>\n\n"
            f"Компания: {company or 'любая'}\n"
            f"Ключевые слова: {', '.join(keywords) if keywords else 'нет'}\n\n"
            f"<i>Функция в разработке.\n"
            f"Используйте веб-интерфейс Plane для поиска задачи.</i>",
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        bot_logger.error(f"Error in voice_find_task callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


def get_transcription_from_cache(cache_key: str) -> Optional[dict]:
    """Get cached transcription data (for webhook handlers)"""
    return _transcription_cache.get(cache_key)


def update_transcription_cache(cache_key: str, data: dict):
    """Update cached transcription data (for webhook handlers)"""
    _transcription_cache[cache_key] = data
