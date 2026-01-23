"""
Voice Message Transcription Handler

Transcribes voice messages using OpenAI Whisper API
and offers to create tasks or journal entries.
"""

import os
import tempfile
import aiohttp
from typing import Optional

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from ..config import settings
from ..utils.logger import bot_logger


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


async def transcribe_with_whisper(file_path: str) -> Optional[str]:
    """
    Transcribe audio file using OpenAI Whisper API.

    Returns transcription text or None on error.
    """
    if not settings.openai_api_key:
        bot_logger.warning("OpenAI API key not configured, cannot transcribe")
        return None

    try:
        url = "https://api.openai.com/v1/audio/transcriptions"
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}"
        }

        async with aiohttp.ClientSession() as session:
            with open(file_path, "rb") as audio_file:
                form = aiohttp.FormData()
                form.add_field("file", audio_file, filename="voice.ogg")
                form.add_field("model", "whisper-1")
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


@router.message(F.voice)
async def handle_voice_message(message: Message, bot: Bot):
    """
    Handle incoming voice messages.

    1. Download voice file
    2. Transcribe with Whisper
    3. Show transcription with action buttons
    """
    # Check if OpenAI is configured
    if not settings.openai_api_key:
        await message.reply(
            "⚠️ Транскрипция голосовых сообщений недоступна.\n"
            "OpenAI API ключ не настроен."
        )
        return

    # Only transcribe for admins (API costs money)
    if not settings.is_admin(message.from_user.id):
        # Silently ignore non-admin voice messages
        return

    # Show "processing" status
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
        await status_msg.edit_text(f"❌ Ошибка: {e}")


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
