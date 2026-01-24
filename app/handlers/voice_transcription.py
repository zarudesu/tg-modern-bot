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


async def get_valid_companies_and_workers() -> tuple[list[str], list[str]]:
    """Fetch valid companies and workers from database."""
    from sqlalchemy import select
    from ..database.database import AsyncSessionLocal
    from ..database.work_journal_models import WorkJournalCompany, WorkJournalWorker

    companies = []
    workers = []

    try:
        async with AsyncSessionLocal() as session:
            # Get companies
            result = await session.execute(
                select(WorkJournalCompany.name)
                .where(WorkJournalCompany.is_active == True)
                .order_by(WorkJournalCompany.display_order)
            )
            companies = [row[0] for row in result.fetchall()]

            # Get workers
            result = await session.execute(
                select(WorkJournalWorker.name)
                .where(WorkJournalWorker.is_active == True)
                .order_by(WorkJournalWorker.display_order)
            )
            workers = [row[0] for row in result.fetchall()]
    except Exception as e:
        bot_logger.warning(f"Failed to fetch companies/workers from DB: {e}")

    return companies, workers


async def extract_report_data_with_ai(transcription: str) -> Optional[dict]:
    """
    Extract work report data from transcription using OpenRouter AI.

    Matches company and worker names to database values.
    """
    openrouter_key = getattr(settings, 'openrouter_api_key', None)
    if not openrouter_key:
        bot_logger.warning("OpenRouter API key not configured")
        return None

    # Get valid values from database
    companies, workers = await get_valid_companies_and_workers()
    companies_list = ", ".join(companies) if companies else "любая"
    workers_list = ", ".join(workers) if workers else "любые"

    # Common aliases for companies (voice may use shortened names)
    company_aliases = """
Company aliases (use the OFFICIAL name on the right):
- "харизма", "хардслабс", "харц", "хардс" → "Харц Лабз"
- "софтфабрик", "софт фабрик", "фабрик" → "СофтФабрик"
- "3д ру", "тридиру", "3д" → "3Д.РУ"
- "сад", "здоровье" → "Сад Здоровья"
- "дельта телеком" → "Дельта"
- "штифтер" → "Стифтер"
- "сосновка" → "Сосновый бор"
- "вёшки", "вешки" → "Вёшки 95"
- "вондига" → "Вондига Парк"
- "цифра" → "ЦифраЦифра"
- "хивп", "эйчхивп" → "HHIVP"
"""

    try:
        async with aiohttp.ClientSession() as session:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {openrouter_key}",
                "Content-Type": "application/json"
            }

            system_prompt = f"""Extract work report data from voice transcription in Russian.
The transcription may contain MULTIPLE work entries (different companies/tasks).

IMPORTANT: Try to match company and worker names to these valid values:
- Valid companies: {companies_list}
- Valid workers: {workers_list}

{company_aliases}

If mentioned name is similar but not exact, use the closest match from the list above.
Voice may use informal/shortened names - always convert to official name!

Respond ONLY with JSON (no markdown, no code blocks):
{{
  "entries": [
    {{
      "work_duration": "Xч" (like "2ч", "4ч", "1.5ч"),
      "is_travel": true/false,
      "workers": ["Имя1", "Имя2"],
      "workers_unmatched": ["Имя"] (names not found in valid list),
      "company": "company name",
      "company_unmatched": true/false (true if not in valid list),
      "work_description": "brief description"
    }}
  ]
}}

Rules:
- Create SEPARATE entry for each company/task mentioned
- If one trip covers multiple companies, create entry per company
- Workers can be shared across entries if they worked together all day
- ALWAYS return mentioned company/workers even if not in valid list
- Set company_unmatched=true or add to workers_unmatched if not matched"""

            payload = {
                "model": "mistralai/devstral-2512:free",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Extract from: {transcription}"}
                ],
                "temperature": 0.2,
                "max_tokens": 500
            }

            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    content = result.get("choices", [{}])[0].get("message", {}).get("content", "{}")

                    # Clean up markdown code blocks if present
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0]
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0]

                    import json
                    return json.loads(content.strip())
                else:
                    error_text = await resp.text()
                    bot_logger.error(f"OpenRouter API error: {resp.status} - {error_text}")
                    return None

    except Exception as e:
        bot_logger.error(f"Error extracting with OpenRouter: {e}")
        return None


async def transcribe_with_whisper(file_path: str) -> Optional[str]:
    """
    Transcribe audio file using Whisper API.

    Supports multiple providers (in priority order):
    1. HuggingFace (free) - HUGGINGFACE_API_KEY
    2. Groq (paid, cheap) - GROQ_API_KEY
    3. OpenAI (paid) - OPENAI_API_KEY

    Returns transcription text or None on error.
    """
    hf_key = getattr(settings, 'huggingface_api_key', None)
    groq_key = getattr(settings, 'groq_api_key', None)
    openai_key = getattr(settings, 'openai_api_key', None)

    try:
        # Read audio file
        with open(file_path, "rb") as f:
            audio_data = f.read()

        async with aiohttp.ClientSession() as session:
            # Try HuggingFace first (free)
            if hf_key:
                bot_logger.info("Using HuggingFace Whisper for transcription")
                # New endpoint (old api-inference.huggingface.co is deprecated as of 2025)
                url = "https://router.huggingface.co/hf-inference/models/openai/whisper-large-v3"
                # Determine content type from file extension
                content_type = "audio/ogg"
                if file_path.endswith(".wav"):
                    content_type = "audio/wav"
                elif file_path.endswith(".mp3"):
                    content_type = "audio/mpeg"
                elif file_path.endswith(".flac"):
                    content_type = "audio/flac"
                headers = {
                    "Authorization": f"Bearer {hf_key}",
                    "Content-Type": content_type
                }

                async with session.post(url, headers=headers, data=audio_data) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        return result.get("text", "").strip()
                    else:
                        error_text = await resp.text()
                        bot_logger.warning(f"HuggingFace API error: {resp.status} - {error_text}")
                        # Fall through to next provider

            # Try Groq (paid but cheap)
            if groq_key:
                bot_logger.info("Using Groq Whisper for transcription")
                url = "https://api.groq.com/openai/v1/audio/transcriptions"
                headers = {"Authorization": f"Bearer {groq_key}"}

                form = aiohttp.FormData()
                form.add_field("file", audio_data, filename="voice.ogg", content_type="audio/ogg")
                form.add_field("model", "whisper-large-v3-turbo")
                form.add_field("language", "ru")
                form.add_field("response_format", "text")

                async with session.post(url, headers=headers, data=form) as resp:
                    if resp.status == 200:
                        return (await resp.text()).strip()
                    else:
                        error_text = await resp.text()
                        bot_logger.warning(f"Groq API error: {resp.status} - {error_text}")

            # Fallback to OpenAI (paid)
            if openai_key:
                bot_logger.info("Using OpenAI Whisper for transcription")
                url = "https://api.openai.com/v1/audio/transcriptions"
                headers = {"Authorization": f"Bearer {openai_key}"}

                form = aiohttp.FormData()
                form.add_field("file", audio_data, filename="voice.ogg", content_type="audio/ogg")
                form.add_field("model", "whisper-1")
                form.add_field("language", "ru")
                form.add_field("response_format", "text")

                async with session.post(url, headers=headers, data=form) as resp:
                    if resp.status == 200:
                        return (await resp.text()).strip()
                    else:
                        error_text = await resp.text()
                        bot_logger.error(f"OpenAI API error: {resp.status} - {error_text}")

        bot_logger.warning("No working Whisper API available")
        return None

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
    - Если OpenRouter настроен: AI Voice Report (транскрипция + извлечение данных)
    - Иначе: только транскрипция с кнопками действий
    """
    # Only process for admins (API costs money)
    if not settings.is_admin(message.from_user.id):
        # Silently ignore non-admin voice messages
        return

    # Check if transcription APIs are configured
    has_hf = bool(getattr(settings, 'huggingface_api_key', None))
    has_groq = bool(getattr(settings, 'groq_api_key', None))
    has_openai = bool(getattr(settings, 'openai_api_key', None))
    has_openrouter = bool(getattr(settings, 'openrouter_api_key', None))
    has_whisper = has_hf or has_groq or has_openai

    if not has_whisper:
        await message.reply(
            "⚠️ Транскрипция голосовых недоступна\n"
            "Настройте HUGGINGFACE_API_KEY",
            parse_mode=None
        )
        return

    # Если есть OpenRouter - используем AI Voice Report с извлечением данных
    if has_openrouter:
        await handle_ai_voice_report(message, bot)
    else:
        # Только транскрипция (без AI извлечения)
        await handle_local_transcription(message, bot)


async def handle_ai_voice_report(message: Message, bot: Bot):
    """
    AI Voice Report - полная автоматизация через OpenRouter.

    Workflow:
    1. Бот получает голосовое
    2. Транскрипция через HuggingFace/Groq/OpenAI Whisper
    3. AI извлечение данных через OpenRouter (бесплатная модель)
    4. Показ результата админу с кнопками действий
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
            await status_msg.edit_text("❌ Не удалось скачать голосовое", parse_mode=None)
            return

        await status_msg.edit_text(
            "🎤 <b>AI Voice Report</b>\n\n"
            "⏳ Транскрибирую (Whisper)...",
            parse_mode="HTML"
        )

        transcription = await transcribe_with_whisper(file_path)
        if not transcription:
            await status_msg.edit_text(
                "❌ Не удалось транскрибировать\n"
                "Проверьте GROQ_API_KEY или OPENAI_API_KEY в настройках",
                parse_mode=None
            )
            return

        await status_msg.edit_text(
            "🎤 <b>AI Voice Report</b>\n\n"
            f"✅ Транскрипция готова ({len(transcription)} симв.)\n"
            "⏳ AI извлекает данные (OpenRouter)...",
            parse_mode="HTML"
        )

        # 2. Извлекаем данные напрямую через OpenRouter (без n8n)
        extraction = await extract_report_data_with_ai(transcription)

        if extraction:
            # Получаем массив записей (новый формат)
            entries = extraction.get('entries', [])

            # Обратная совместимость: если старый формат (без entries)
            if not entries and extraction.get('work_duration'):
                entries = [extraction]

            # Сохраняем для дальнейшей обработки
            cache_key = f"voice_report:{message.from_user.id}:{message.message_id}"
            _transcription_cache[cache_key] = {
                "transcription": transcription,
                "entries": entries,
                "status_message_id": status_msg.message_id,
                "chat_id": message.chat.id,
                "duration": message.voice.duration
            }

            # Формируем красивый результат для всех записей
            entries_text = ""
            for i, entry in enumerate(entries, 1):
                work_duration = entry.get('work_duration', '?')
                is_travel = entry.get('is_travel', False)
                workers = entry.get('workers', [])
                company = entry.get('company', '?')
                work_description = entry.get('work_description', '')

                workers_str = ", ".join(workers) if workers else "не указаны"
                travel_str = "✅ Выезд" if is_travel else "🏠 Удалённо"

                entries_text += (
                    f"\n<b>📋 Запись {i}:</b>\n"
                    f"🏢 {company or '?'} | ⏱ {work_duration} | {travel_str}\n"
                    f"👥 {workers_str}\n"
                    f"📝 {work_description[:80]}{'...' if len(work_description) > 80 else ''}\n"
                )

            total_entries = len(entries)
            header = f"🎤 <b>AI Voice Report</b> ({total_entries} {'запись' if total_entries == 1 else 'записей' if total_entries < 5 else 'записей'})\n"

            await status_msg.edit_text(
                f"{header}\n"
                f"<b>📝 Транскрипция:</b>\n"
                f"<i>{transcription[:200]}{'...' if len(transcription) > 200 else ''}</i>\n"
                f"{entries_text}\n"
                f"<i>Нажмите кнопку для создания записей</i>",
                parse_mode="HTML",
                reply_markup=create_voice_result_keyboard(message.from_user.id, message.message_id)
            )

            bot_logger.info(
                f"Voice transcribed: {total_entries} entries extracted",
                extra={
                    "admin_id": message.from_user.id,
                    "duration": message.voice.duration,
                    "entries_count": total_entries
                }
            )
        else:
            # AI extraction не удался - показываем только транскрипцию
            bot_logger.warning("AI extraction failed, showing plain transcription")

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
        status_msg = await message.reply("🎤 Транскрибирую голосовое сообщение", parse_mode=None)

    try:
        # 1. Download voice file
        file_path = await download_voice_file(bot, message.voice.file_id)
        if not file_path:
            await status_msg.edit_text("❌ Не удалось скачать голосовое сообщение", parse_mode=None)
            return

        # 2. Transcribe with Whisper
        transcription = await transcribe_with_whisper(file_path)
        if not transcription:
            await status_msg.edit_text("❌ Не удалось транскрибировать сообщение", parse_mode=None)
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
            error_text = str(e).replace("<", "&lt;").replace(">", "&gt;")
            await callback.message.edit_text(f"❌ Ошибка: {error_text}", parse_mode="HTML")

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
    """Create work journal entries from AI extraction (supports multiple)"""
    try:
        parts = callback.data.split(":")
        admin_id = int(parts[1])
        message_id = int(parts[2])

        cache_key = f"voice_report:{admin_id}:{message_id}"
        cached = _transcription_cache.get(cache_key)

        if not cached:
            await callback.answer("❌ Данные истекли", show_alert=True)
            return

        entries = cached.get("entries", [])
        transcription = cached.get("transcription", "")

        # Обратная совместимость
        if not entries and cached.get("extraction"):
            entries = [cached.get("extraction")]

        if not entries:
            await callback.answer("❌ Нет данных для журнала", show_alert=True)
            return

        # Формируем текст для всех записей
        entries_text = f"<b>📋 Данные для журнала работ ({len(entries)} записей):</b>\n\n"

        for i, entry in enumerate(entries, 1):
            work_duration = entry.get("work_duration", "?")
            is_travel = entry.get("is_travel", False)
            workers = entry.get("workers", [])
            company = entry.get("company", "")
            work_description = entry.get("work_description", "")

            workers_str = ", ".join(workers) if workers else "не указаны"
            travel_str = "✅ Выезд" if is_travel else "🏠 Удалённо"

            entries_text += (
                f"<b>Запись {i}:</b>\n"
                f"🏢 {company or '?'} | ⏱ {work_duration} | {travel_str}\n"
                f"👥 {workers_str}\n"
                f"📝 {work_description[:100]}\n\n"
            )

        entries_text += "<i>Используйте /journal для создания записей</i>"

        await callback.message.edit_text(entries_text, parse_mode="HTML")

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
