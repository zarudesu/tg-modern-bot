"""
Work Journal Commands - Основные команды (/journal, /history, /report, /companies)
"""
from datetime import date, datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from ...utils.logger import bot_logger, log_user_action

router = Router()


@router.message(Command("journal", "work_journal"))
async def start_journal_entry(message: Message):
    """Начать создание записи в журнале работ"""
    try:
        user_id = message.from_user.id
        log_user_action(user_id, "start_journal")
        
        # Здесь будет полная логика создания записи
        await message.answer(
            "📋 **Журнал работ**\n\n🚧 Модульная версия в разработке\n\nИспользуйте старую команду пока что",
            parse_mode="MarkdownV2"
        )
        
    except Exception as e:
        bot_logger.error(f"Error starting journal entry for user {user_id}: {e}")
        await message.answer(
            "❌ Произошла ошибка\\. Попробуйте позже\\.",
            parse_mode="MarkdownV2"
        )


@router.message(Command("history", "work_history"))
async def show_work_history(message: Message):
    """Показать историю работ"""
    try:
        user_id = message.from_user.id
        log_user_action(user_id, "view_history")
        
        await message.answer(
            "📊 **История работ**\n\n🚧 Модульная версия в разработке",
            parse_mode="MarkdownV2"
        )
        
    except Exception as e:
        bot_logger.error(f"Error showing work history for user {user_id}: {e}")
        await message.answer(
            "❌ Произошла ошибка\\. Попробуйте позже\\.",
            parse_mode="MarkdownV2"
        )


@router.message(Command("report", "work_report"))
async def show_work_report(message: Message):
    """Показать отчеты по работам"""
    try:
        user_id = message.from_user.id
        log_user_action(user_id, "view_reports")
        
        await message.answer(
            "📈 **Отчеты**\n\n🚧 Модульная версия в разработке",
            parse_mode="MarkdownV2"
        )
        
    except Exception as e:
        bot_logger.error(f"Error showing work reports for user {user_id}: {e}")
        await message.answer(
            "❌ Произошла ошибка\\. Попробуйте позже\\.",
            parse_mode="MarkdownV2"
        )


@router.message(Command("companies", "manage_companies"))
async def manage_companies(message: Message):
    """Управление списком компаний"""
    try:
        user_id = message.from_user.id
        log_user_action(user_id, "manage_companies")
        
        await message.answer(
            "🏢 **Управление компаниями**\n\n🚧 Модульная версия в разработке",
            parse_mode="MarkdownV2"
        )
        
    except Exception as e:
        bot_logger.error(f"Error managing companies for user {user_id}: {e}")
        await message.answer(
            "❌ Произошла ошибка\\. Попробуйте позже\\.",
            parse_mode="MarkdownV2"
        )
