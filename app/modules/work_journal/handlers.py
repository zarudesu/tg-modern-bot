"""
Обработчики команд для модуля журнала работ
"""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from datetime import date, timedelta

from ...database.database import get_async_session
from ...services.work_journal_service import WorkJournalService
from ...utils.work_journal_constants import WorkJournalState, MESSAGE_TEMPLATES
from ...utils.work_journal_keyboards import (
    create_date_selection_keyboard,
    create_history_menu_keyboard,
    create_report_menu_keyboard
)
from ...utils.work_journal_formatters import (
    escape_markdown_v2,
    format_entries_list,
    format_statistics_report,
    format_error_message
)
from ...utils.logger import bot_logger, log_user_action

router = Router()


@router.message(Command("journal", "work_journal"))
async def start_journal_entry(message: Message):
    """Начать создание записи в журнале работ"""
    try:
        user_id = message.from_user.id
        log_user_action(user_id, "start_journal")
        
        async for session in get_async_session():
            service = WorkJournalService(session)
            
            # Очищаем предыдущее состояние и устанавливаем начальное
            await service.set_user_state(
                user_id,
                WorkJournalState.SELECTING_DATE,
                draft_date=date.today()  # По умолчанию сегодняшняя дата
            )
            
            # Отправляем стартовое сообщение
            start_text = (
                f"{MESSAGE_TEMPLATES['start_entry']}\n\n"
                f"📅 Выберите дату работ:"
            )
            
            await message.answer(
                start_text,
                reply_markup=create_date_selection_keyboard(),
                parse_mode="MarkdownV2"
            )
            
    except Exception as e:
        bot_logger.error(f"Error starting journal entry for user {user_id}: {e}")
        await message.answer(
            format_error_message("general"),
            parse_mode="MarkdownV2"
        )


@router.message(Command("companies", "manage_companies"))
async def manage_companies(message: Message):
    """Управление списком компаний"""
    try:
        user_id = message.from_user.id
        log_user_action(user_id, "manage_companies")
        
        async for session in get_async_session():
            service = WorkJournalService(session)
            
            # Получаем список всех компаний
            companies = await service.get_companies()
            
            if not companies:
                companies_text = (
                    "🏢 *Управление компаниями*\n\n"
                    "❌ Список компаний пуст\\.\n\n"
                    "Компании автоматически добавляются при создании записей\\."
                )
            else:
                companies_text = "🏢 *Список компаний:*\n\n"
                for i, company in enumerate(companies, 1):
                    escaped_company = escape_markdown_v2(company)
                    companies_text += f"{i}\\. {escaped_company}\n"
                
                companies_text += (
                    f"\n*Всего компаний:* {len(companies)}\n\n"
                    f"Для удаления используйте:\n"
                    f"`/delete_company Название`"
                )
            
            await message.answer(
                companies_text,
                parse_mode="MarkdownV2"
            )
            
    except Exception as e:
        bot_logger.error(f"Error managing companies for user {user_id}: {e}")
        await message.answer("Произошла ошибка при получении списка компаний\\.")


@router.message(Command("delete_company"))
async def delete_company(message: Message):
    """Удаление компании из списка"""
    try:
        user_id = message.from_user.id
        
        # Извлекаем название компании из команды
        command_parts = message.text.split(maxsplit=1)
        if len(command_parts) < 2:
            await message.answer(
                "❌ *Укажите название компании*\n\nПример: `/delete_company Test`\n\nДля просмотра списка: `/companies`",
                parse_mode="MarkdownV2"
            )
            return
        
        company_name = command_parts[1].strip()
        log_user_action(user_id, f"delete_company_{company_name}")
        
        async for session in get_async_session():
            service = WorkJournalService(session)
            
            # Проверяем, существует ли компания
            companies = await service.get_companies()
            if company_name not in companies:
                await message.answer(
                    f"❌ *Компания не найдена*\n\nКомпания \"{escape_markdown_v2(company_name)}\" не найдена в списке\\.",
                    parse_mode="MarkdownV2"
                )
                return
            
            # Проверяем, есть ли записи с этой компанией
            entries_count = await service.count_entries_by_company(company_name)
            
            if entries_count > 0:
                await message.answer(
                    f"⚠️ *Нельзя удалить компанию*\n\n"
                    f"Компания \"{escape_markdown_v2(company_name)}\" используется в {entries_count} записях\\.\n\n"
                    f"Для принудительного удаления со всеми записями:\n"
                    f"`/force_delete_company {company_name}`",
                    parse_mode="MarkdownV2"
                )
                return
            
            # Удаляем компанию
            success = await service.delete_company(company_name)
            
            if success:
                await message.answer(
                    f"✅ *Компания удалена*\n\nКомпания \"{escape_markdown_v2(company_name)}\" успешно удалена\\.",
                    parse_mode="MarkdownV2"
                )
                log_user_action(user_id, f"deleted_company_{company_name}")
            else:
                await message.answer(
                    f"❌ *Ошибка удаления*\n\nПроизошла ошибка при удалении компании \"{escape_markdown_v2(company_name)}\"\\.",
                    parse_mode="MarkdownV2"
                )
                
    except Exception as e:
        bot_logger.error(f"Error deleting company for user {user_id}: {e}")
        await message.answer("Произошла ошибка при удалении компании\\.")


@router.message(Command("force_delete_company"))
async def force_delete_company(message: Message):
    """Принудительное удаление компании со всеми связанными записями"""
    try:
        user_id = message.from_user.id
        
        # Извлекаем название компании из команды
        command_parts = message.text.split(maxsplit=1)
        if len(command_parts) < 2:
            await message.answer(
                "❌ *Укажите название компании*\n\n"
                "⚠️ *ВНИМАНИЕ\\!* Эта команда удалит компанию и ВСЕ связанные записи\\!\n\n"
                "Пример: `/force_delete_company Test`",
                parse_mode="MarkdownV2"
            )
            return
        
        company_name = command_parts[1].strip()
        log_user_action(user_id, f"force_delete_company_{company_name}")
        
        async for session in get_async_session():
            service = WorkJournalService(session)
            
            # Проверяем, существует ли компания
            companies = await service.get_companies()
            if company_name not in companies:
                await message.answer(
                    f"❌ *Компания не найдена*\n\nКомпания \"{escape_markdown_v2(company_name)}\" не найдена в списке\\.",
                    parse_mode="MarkdownV2"
                )
                return
            
            # Получаем количество записей для информации
            entries_count = await service.count_entries_by_company(company_name)
            
            # Принудительно удаляем компанию со всеми записями
            success = await service.force_delete_company_with_entries(company_name)
            
            if success:
                if entries_count > 0:
                    await message.answer(
                        f"✅ *Компания и записи удалены*\n\n"
                        f"Компания \"{escape_markdown_v2(company_name)}\" удалена вместе с *{entries_count}* записями\\.",
                        parse_mode="MarkdownV2"
                    )
                    log_user_action(user_id, f"force_deleted_company_{company_name}_with_{entries_count}_entries")
                else:
                    await message.answer(
                        f"✅ *Компания удалена*\n\nКомпания \"{escape_markdown_v2(company_name)}\" успешно удалена\\.",
                        parse_mode="MarkdownV2"
                    )
                    log_user_action(user_id, f"force_deleted_company_{company_name}")
            else:
                await message.answer(
                    f"❌ *Ошибка удаления*\n\nПроизошла ошибка при принудительном удалении компании\\.",
                    parse_mode="MarkdownV2"
                )
            
    except Exception as e:
        bot_logger.error(f"Error force deleting company for user {user_id}: {e}")
        await message.answer("Произошла ошибка при принудительном удалении компании\\.")


@router.message(Command("history", "work_history"))
async def show_work_history(message: Message):
    """Показать историю работ"""
    try:
        user_id = message.from_user.id
        log_user_action(user_id, "show_history")
        
        async for session in get_async_session():
            service = WorkJournalService(session)
            
            # Получаем последние записи (например, за последние 30 дней)
            end_date = date.today()
            start_date = end_date - timedelta(days=30)
            
            entries = await service.get_entries_by_date_range(
                user_id, start_date, end_date
            )
            
            if not entries:
                await message.answer(
                    "📊 *История работ*\n\n"
                    "❌ Записи за последние 30 дней не найдены\\.\n\n"
                    "Для создания записи используйте /journal",
                    parse_mode="MarkdownV2"
                )
                return
            
            # Форматируем и отправляем список записей
            formatted_entries = format_entries_list(entries, limit=10)
            
            history_text = (
                f"📊 *История работ* \\(последние 30 дней\\)\n\n"
                f"{formatted_entries}\n"
                f"*Всего записей:* {len(entries)}"
            )
            
            if len(entries) > 10:
                history_text += f"\n\n🔍 Показаны последние 10 записей из {len(entries)}"
            
            await message.answer(
                history_text,
                reply_markup=create_history_menu_keyboard(),
                parse_mode="MarkdownV2"
            )
            
    except Exception as e:
        bot_logger.error(f"Error showing history for user {user_id}: {e}")
        await message.answer(
            format_error_message("general"),
            parse_mode="MarkdownV2"
        )


@router.message(Command("report", "work_report"))
async def show_work_report(message: Message):
    """Показать отчет по работам"""
    try:
        user_id = message.from_user.id
        log_user_action(user_id, "show_report")
        
        async for session in get_async_session():
            service = WorkJournalService(session)
            
            # Получаем статистику за текущий месяц
            today = date.today()
            start_of_month = today.replace(day=1)
            
            entries = await service.get_entries_by_date_range(
                user_id, start_of_month, today
            )
            
            if not entries:
                await message.answer(
                    "📈 *Отчет по работам*\n\n"
                    "❌ Записи за текущий месяц не найдены\\.\n\n"
                    "Для создания записи используйте /journal",
                    parse_mode="MarkdownV2"
                )
                return
            
            # Генерируем статистический отчет
            report_data = await service.generate_statistics_report(
                user_id, start_of_month, today
            )
            
            formatted_report = format_statistics_report(report_data, start_of_month, today)
            
            await message.answer(
                formatted_report,
                reply_markup=create_report_menu_keyboard(),
                parse_mode="MarkdownV2"
            )
            
    except Exception as e:
        bot_logger.error(f"Error showing report for user {user_id}: {e}")
        await message.answer(
            format_error_message("general"),
            parse_mode="MarkdownV2"
        )
