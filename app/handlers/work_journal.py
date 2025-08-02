"""
Обработчики команд модуля журнала работ
"""
from datetime import date, datetime, timedelta
from typing import Optional, Union, Tuple
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.database import get_async_session
from ..database.models import BotUser
from ..services.work_journal_service import WorkJournalService
from ..services.n8n_integration_service import N8nIntegrationService
from ..utils.work_journal_constants import (
    WorkJournalState, 
    CallbackAction, 
    EMOJI,
    MESSAGE_TEMPLATES
)
from ..utils.work_journal_keyboards import (
    parse_callback_data,
    create_date_selection_keyboard,
    create_company_selection_keyboard,
    create_duration_selection_keyboard,
    create_travel_selection_keyboard,
    create_worker_selection_keyboard,
    create_confirmation_keyboard,
    create_description_keyboard,
    create_continue_keyboard,
    create_history_menu_keyboard,
    create_report_menu_keyboard
)
from ..utils.work_journal_formatters import (
    escape_markdown_v2,
    format_date_for_display,
    format_draft_confirmation,
    format_error_message,
    format_success_message,
    format_entries_list,
    format_statistics_report,
    format_help_message
)
from ..utils.logger import bot_logger, log_user_action
from sqlalchemy import select

router = Router()


async def get_user_email(session: AsyncSession, telegram_user_id: int) -> Optional[str]:
    """Получить email пользователя"""
    result = await session.execute(
        select(BotUser).where(BotUser.telegram_user_id == telegram_user_id)
    )
    user = result.scalar_one_or_none()
    
    if user and user.username:
        return f"{user.username}@example.com"  # Можно настроить формат email
    
    return f"user_{telegram_user_id}@telegram.bot"


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
                f"{EMOJI['date']} *Дата:* {escape_markdown_v2(format_date_for_display(date.today()))}"
            )
            
            await message.answer(
                start_text,
                reply_markup=create_continue_keyboard(),
                parse_mode="MarkdownV2"
            )
            
    except Exception as e:
        bot_logger.error(f"Error starting journal entry for user {user_id}: {e}")
        await message.answer(
            format_error_message("general"),
            parse_mode="MarkdownV2"
        )


@router.callback_query(F.data.startswith("wj:"))
async def handle_journal_callback(callback: CallbackQuery):
    """Обработчик callback-запросов журнала работ"""
    try:
        user_id = callback.from_user.id
        action, data = parse_callback_data(callback.data)
        
        async for session in get_async_session():
            service = WorkJournalService(session)
            user_state = await service.get_user_state(user_id)
            
            if not user_state:
                await callback.answer("Сессия истекла. Начните заново с команды /journal", show_alert=True)
                return
            
            # Обрабатываем действия по типу
            if action == CallbackAction.CONTINUE.value:
                await handle_continue_action(callback, session, service, user_state)
            
            elif action == CallbackAction.SELECT_TODAY.value:
                await handle_date_selection(callback, session, service, date.today())
            
            elif action == CallbackAction.SELECT_YESTERDAY.value:
                yesterday = date.today() - timedelta(days=1)
                await handle_date_selection(callback, session, service, yesterday)
            
            elif action == CallbackAction.SELECT_COMPANY.value:
                await handle_company_selection(callback, session, service, data)
            
            elif action == CallbackAction.SELECT_DURATION.value:
                await handle_duration_selection(callback, session, service, data)
            
            elif action == CallbackAction.SELECT_TRAVEL_YES.value:
                await handle_travel_selection(callback, session, service, True)
            
            elif action == CallbackAction.SELECT_TRAVEL_NO.value:
                await handle_travel_selection(callback, session, service, False)
            
            elif action == CallbackAction.TOGGLE_WORKER.value:
                await handle_toggle_worker(callback, session, service, data)
            
            elif action == CallbackAction.CONFIRM_WORKERS.value:
                await handle_confirm_workers(callback, session, service)
            
            elif action == CallbackAction.SELECT_WORKER.value:
                # Для обратной совместимости - одиночный выбор
                await handle_single_worker_selection(callback, session, service, data)
            
            elif action == CallbackAction.CONFIRM_SAVE.value:
                await handle_confirm_save(callback, session, service, user_state)
            
            elif action == CallbackAction.CANCEL.value:
                await handle_cancel_action(callback, session, service)
            
            elif action == CallbackAction.BACK.value:
                await handle_back_action(callback, session, service, user_state)
            
            else:
                await callback.answer("Неизвестное действие")
                
    except Exception as e:
        bot_logger.error(f"Error handling journal callback {callback.data} for user {user_id}: {e}")
        await callback.answer("Произошла ошибка. Попробуйте позже.", show_alert=True)


async def handle_continue_action(
    callback: CallbackQuery,
    session: AsyncSession, 
    service: WorkJournalService,
    user_state
):
    """Обработчик действия 'Продолжить'"""
    if user_state.current_state == WorkJournalState.SELECTING_DATE.value:
        # Переходим к выбору компании
        companies = await service.get_companies()
        
        await service.set_user_state(
            callback.from_user.id,
            WorkJournalState.SELECTING_COMPANY
        )
        
        await callback.message.edit_text(
            MESSAGE_TEMPLATES['company_selection'],
            reply_markup=create_company_selection_keyboard(companies),
            parse_mode="MarkdownV2"
        )
        
        await callback.answer()


async def handle_date_selection(
    callback: CallbackQuery,
    session: AsyncSession,
    service: WorkJournalService,
    selected_date: date
):
    """Обработчик выбора даты"""
    await service.set_user_state(
        callback.from_user.id,
        WorkJournalState.SELECTING_COMPANY,
        draft_date=selected_date
    )
    
    companies = await service.get_companies()
    
    await callback.message.edit_text(
        MESSAGE_TEMPLATES['company_selection'],
        reply_markup=create_company_selection_keyboard(companies),
        parse_mode="MarkdownV2"
    )
    
    await callback.answer(f"Выбрана дата: {format_date_for_display(selected_date)}")


async def handle_company_selection(
    callback: CallbackQuery,
    session: AsyncSession,
    service: WorkJournalService,
    company: str
):
    """Обработчик выбора компании"""
    await service.set_user_state(
        callback.from_user.id,
        WorkJournalState.SELECTING_DURATION,
        draft_company=company
    )
    
    await callback.message.edit_text(
        MESSAGE_TEMPLATES['duration_selection'],
        reply_markup=create_duration_selection_keyboard(),
        parse_mode="MarkdownV2"
    )
    
    await callback.answer(f"Выбрана компания: {company}")


async def handle_duration_selection(
    callback: CallbackQuery,
    session: AsyncSession,
    service: WorkJournalService,
    duration: str
):
    """Обработчик выбора длительности"""
    await service.set_user_state(
        callback.from_user.id,
        WorkJournalState.ENTERING_DESCRIPTION,
        draft_duration=duration
    )
    
    await callback.message.edit_text(
        MESSAGE_TEMPLATES['description_prompt'],
        reply_markup=create_description_keyboard(),
        parse_mode="MarkdownV2"
    )
    
    await callback.answer(f"Выбрано время: {duration}")


async def handle_travel_selection(
    callback: CallbackQuery,
    session: AsyncSession,
    service: WorkJournalService,
    is_travel: bool
):
    """Обработчик выбора типа работ (выезд/удаленно)"""
    await service.set_user_state(
        callback.from_user.id,
        WorkJournalState.SELECTING_WORKER,
        draft_is_travel=is_travel
    )
    
    workers = await service.get_workers()
    
    await callback.message.edit_text(
        MESSAGE_TEMPLATES['worker_selection'],
        reply_markup=create_worker_selection_keyboard(workers, []),  # Пустой список выбранных
        parse_mode="MarkdownV2"
    )
    
    travel_text = "выезд" if is_travel else "удаленная работа"
    await callback.answer(f"Выбрано: {travel_text}")


async def handle_worker_selection(
    callback: CallbackQuery,
    session: AsyncSession,
    service: WorkJournalService,
    worker: str
):
    """Обработчик выбора исполнителя (DEPRECATED - используйте множественный выбор)"""
    import json
    
    await service.set_user_state(
        callback.from_user.id,
        WorkJournalState.CONFIRMING_ENTRY,
        draft_workers=json.dumps([worker], ensure_ascii=False)
    )
    
    # Получаем обновленное состояние для отображения
    user_state = await service.get_user_state(callback.from_user.id)
    
    confirmation_text = format_draft_confirmation(user_state)
    
    await callback.message.edit_text(
        confirmation_text,
        reply_markup=create_confirmation_keyboard(),
        parse_mode="MarkdownV2"
    )
    
    await callback.answer(f"Выбран исполнитель: {worker}")


async def handle_confirm_save(
    callback: CallbackQuery,
    session: AsyncSession,
    service: WorkJournalService,
    user_state
):
    """Обработчик подтверждения сохранения"""
    try:
        # Проверяем, что все данные заполнены
        if not all([
            user_state.draft_date,
            user_state.draft_company,
            user_state.draft_duration,
            user_state.draft_description,
            user_state.draft_workers,
            user_state.draft_is_travel is not None
        ]):
            await callback.answer("Не все поля заполнены!", show_alert=True)
            return
        
        # Парсим список исполнителей
        try:
            import json
            worker_names = json.loads(user_state.draft_workers)
            if not worker_names:
                await callback.answer("Выберите хотя бы одного исполнителя!", show_alert=True)
                return
        except (json.JSONDecodeError, TypeError):
            await callback.answer("Ошибка в данных исполнителей!", show_alert=True)
            return
        
        # Получаем информацию о создателе записи
        creator_name, user_email = await get_user_info(session, callback.from_user.id)
        
        # Создаем запись в БД
        entry = await service.create_work_entry(
            telegram_user_id=callback.from_user.id,
            user_email=user_email,
            work_date=user_state.draft_date,
            company=user_state.draft_company,
            work_duration=user_state.draft_duration,
            work_description=user_state.draft_description,
            is_travel=user_state.draft_is_travel,
            worker_names=worker_names,
            created_by_user_id=callback.from_user.id,
            created_by_name=creator_name
        )
        
        # Очищаем состояние пользователя
        await service.clear_user_state(callback.from_user.id)
        
        # Отправляем в n8n (асинхронно)
        try:
            # Получаем данные пользователя для n8n
            result = await session.execute(
                select(BotUser).where(BotUser.telegram_user_id == callback.from_user.id)
            )
            user = result.scalar_one_or_none()
            
            user_data = {
                "first_name": user.first_name if user else callback.from_user.first_name,
                "username": user.username if user else callback.from_user.username
            }
            
            n8n_service = N8nIntegrationService()
            await n8n_service.send_with_retry(entry, user_data, session)
            
        except Exception as e:
            bot_logger.error(f"Error sending to n8n for entry {entry.id}: {e}")
            # Не прерываем процесс, так как запись уже сохранена в БД
        
        # Формируем сообщение об успехе с деталями
        workers_text = ", ".join(worker_names)
        work_date_str = user_state.draft_date.strftime('%d.%m.%Y') if user_state.draft_date else "Не указана"
        success_message = (
            f"{format_success_message('created')}\n\n"
            f"*Детали записи:*\n"
            f"📅 Дата: {work_date_str}\n"
            f"🏢 Компания: {user_state.draft_company or 'Не указана'}\n"
            f"⏱ Время: {user_state.draft_duration or 'Не указано'}\n"
            f"👥 Исполнители: {workers_text}\n"
            f"🚗 Тип: {'Выезд' if user_state.draft_is_travel else 'Удаленно'}\n"
            f"👤 Создал: {creator_name}"
        )
        
        await callback.message.edit_text(
            success_message,
            parse_mode="MarkdownV2"
        )
        
        log_user_action(callback.from_user.id, "journal_entry_created")
        await callback.answer("Запись сохранена!")
        
        # Отправляем уведомления с упоминаниями исполнителей
        try:
            from ..services.worker_mention_service import WorkerMentionService
            from aiogram import Bot
            from ..config import settings
            
            bot = Bot(token=settings.telegram_token)
            mention_service = WorkerMentionService(session, bot)
            
            # Отправляем уведомления в чат
            success, errors = await mention_service.send_work_assignment_notifications(
                entry, creator_name, callback.message.chat.id
            )
            
            if errors:
                for error in errors[:2]:  # Показываем только первые 2 ошибки
                    bot_logger.warning(f"Mention notification error: {error}")
                    
        except Exception as e:
            bot_logger.error(f"Error sending mention notifications: {e}")
            # Не прерываем процесс, так как основная задача выполнена
        
    except Exception as e:
        bot_logger.error(f"Error saving work entry: {e}")
        await callback.message.edit_text(
            format_error_message("general"),
            parse_mode="MarkdownV2"
        )
        await callback.answer("Ошибка при сохранении!", show_alert=True)


async def handle_cancel_action(
    callback: CallbackQuery,
    session: AsyncSession,
    service: WorkJournalService
):
    """Обработчик отмены"""
    await service.clear_user_state(callback.from_user.id)
    
    await callback.message.edit_text(
        f"{EMOJI['cross']} Создание записи отменено\\.",
        parse_mode="MarkdownV2"
    )
    
    await callback.answer("Отменено")


async def handle_back_action(
    callback: CallbackQuery,
    session: AsyncSession,
    service: WorkJournalService,
    user_state
):
    """Обработчик возврата назад"""
    current_state = user_state.current_state
    
    if current_state == WorkJournalState.SELECTING_COMPANY.value:
        # Возврат к выбору даты
        await service.set_user_state(
            callback.from_user.id,
            WorkJournalState.SELECTING_DATE
        )
        
        date_str = format_date_for_display(user_state.draft_date) if user_state.draft_date else format_date_for_display(date.today())
        start_text = (
            f"{MESSAGE_TEMPLATES['start_entry']}\n\n"
            f"{EMOJI['date']} **Дата:** {escape_markdown_v2(date_str)}"
        )
        
        await callback.message.edit_text(
            start_text,
            reply_markup=create_continue_keyboard(),
            parse_mode="MarkdownV2"
        )
    
    elif current_state == WorkJournalState.SELECTING_DURATION.value:
        # Возврат к выбору компании
        companies = await service.get_companies()
        
        await service.set_user_state(
            callback.from_user.id,
            WorkJournalState.SELECTING_COMPANY
        )
        
        await callback.message.edit_text(
            MESSAGE_TEMPLATES['company_selection'],
            reply_markup=create_company_selection_keyboard(companies),
            parse_mode="MarkdownV2"
        )
    
    elif current_state == WorkJournalState.ENTERING_DESCRIPTION.value:
        # Возврат к выбору длительности
        await service.set_user_state(
            callback.from_user.id,
            WorkJournalState.SELECTING_DURATION
        )
        
        await callback.message.edit_text(
            MESSAGE_TEMPLATES['duration_selection'],
            reply_markup=create_duration_selection_keyboard(),
            parse_mode="MarkdownV2"
        )
    
    elif current_state == WorkJournalState.SELECTING_TRAVEL.value:
        # Возврат к вводу описания
        await service.set_user_state(
            callback.from_user.id,
            WorkJournalState.ENTERING_DESCRIPTION
        )
        
        await callback.message.edit_text(
            MESSAGE_TEMPLATES['description_prompt'],
            reply_markup=create_description_keyboard(),
            parse_mode="MarkdownV2"
        )
    
    elif current_state == WorkJournalState.SELECTING_WORKER.value:
        # Возврат к выбору выезда
        await service.set_user_state(
            callback.from_user.id,
            WorkJournalState.SELECTING_TRAVEL
        )
        
        await callback.message.edit_text(
            MESSAGE_TEMPLATES['travel_selection'],
            reply_markup=create_travel_selection_keyboard(),
            parse_mode="MarkdownV2"
        )
    
    elif current_state == WorkJournalState.CONFIRMING_ENTRY.value:
        # Возврат к выбору исполнителя
        workers = await service.get_workers()
        
        # Получаем текущий выбор исполнителей
        selected_workers = []
        if user_state.draft_workers:
            try:
                import json
                selected_workers = json.loads(user_state.draft_workers)
            except (json.JSONDecodeError, TypeError):
                pass
        
        await service.set_user_state(
            callback.from_user.id,
            WorkJournalState.SELECTING_WORKER
        )
        
        await callback.message.edit_text(
            MESSAGE_TEMPLATES['worker_selection'],
            reply_markup=create_worker_selection_keyboard(workers, selected_workers),
            parse_mode="MarkdownV2"
        )
    
    await callback.answer()


@router.message(F.text, F.func(lambda msg: msg.text and not msg.text.startswith("/")))
async def handle_text_input(message: Message):
    """Обработчик текстового ввода (описание работ)"""
    try:
        user_id = message.from_user.id
        
        async for session in get_async_session():
            service = WorkJournalService(session)
            user_state = await service.get_user_state(user_id)
            
            if not user_state or user_state.current_state != WorkJournalState.ENTERING_DESCRIPTION.value:
                # Если пользователь не в состоянии ввода описания, игнорируем
                return
            
            # Сохраняем описание и переходим к выбору типа работ
            await service.set_user_state(
                user_id,
                WorkJournalState.SELECTING_TRAVEL,
                draft_description=message.text
            )
            
            await message.answer(
                MESSAGE_TEMPLATES['travel_selection'],
                reply_markup=create_travel_selection_keyboard(),
                parse_mode="MarkdownV2"
            )
            
    except Exception as e:
        bot_logger.error(f"Error handling text input for user {user_id}: {e}")


@router.message(Command("history", "work_history"))
async def show_work_history(message: Message):
    """Показать историю работ"""
    try:
        user_id = message.from_user.id
        log_user_action(user_id, "view_history")
        
        async for session in get_async_session():
            service = WorkJournalService(session)
            
            # Получаем последние 10 записей пользователя
            entries = await service.get_work_entries(
                telegram_user_id=user_id,
                limit=10
            )
            
            if entries:
                text = format_entries_list(entries, "Последние записи")
            else:
                text = f"*{EMOJI['history']} История работ*\n\nУ вас пока нет записей\\. Создайте первую запись командой /journal\\."
            
            await message.answer(
                text,
                reply_markup=create_history_menu_keyboard(),
                parse_mode="MarkdownV2"
            )
            
    except Exception as e:
        bot_logger.error(f"Error showing work history for user {user_id}: {e}")
        await message.answer(
            format_error_message("general"),
            parse_mode="MarkdownV2"
        )


@router.message(Command("report", "work_report"))
async def show_work_reports(message: Message):
    """Показать отчеты по работам"""
    try:
        user_id = message.from_user.id
        log_user_action(user_id, "view_reports")
        
        async for session in get_async_session():
            service = WorkJournalService(session)
            
            # Получаем статистику за последнюю неделю
            week_ago = date.today() - timedelta(days=7)
            stats = await service.get_statistics(
                telegram_user_id=user_id,
                date_from=week_ago
            )
            
            report_text = format_statistics_report(stats, "Отчет за неделю")
            
            await message.answer(
                report_text,
                reply_markup=create_report_menu_keyboard(),
                parse_mode="MarkdownV2"
            )
            
    except Exception as e:
        bot_logger.error(f"Error showing work reports for user {user_id}: {e}")
        await message.answer(
            format_error_message("general"),
            parse_mode="MarkdownV2"
        )


async def handle_toggle_worker(
    callback: CallbackQuery,
    session: AsyncSession,
    service: WorkJournalService,
    worker_name: str
):
    """Обработчик переключения выбора исполнителя"""
    user_state = await service.get_user_state(callback.from_user.id)
    
    # Получаем текущий список выбранных исполнителей
    selected_workers = []
    if user_state.draft_workers:
        try:
            import json
            selected_workers = json.loads(user_state.draft_workers)
        except (json.JSONDecodeError, TypeError):
            selected_workers = []
    
    # Переключаем выбор
    if worker_name in selected_workers:
        selected_workers.remove(worker_name)
    else:
        selected_workers.append(worker_name)
    
    # Сохраняем обновленный список
    import json
    await service.set_user_state(
        callback.from_user.id,
        WorkJournalState.SELECTING_WORKER,
        draft_workers=json.dumps(selected_workers, ensure_ascii=False)
    )
    
    # Обновляем клавиатуру
    workers = await service.get_workers()
    
    await callback.message.edit_text(
        MESSAGE_TEMPLATES['worker_selection'],
        reply_markup=create_worker_selection_keyboard(workers, selected_workers),
        parse_mode="MarkdownV2"
    )
    
    action_text = "добавлен" if worker_name in selected_workers else "удален"
    await callback.answer(f"{worker_name} {action_text}")


async def handle_confirm_workers(
    callback: CallbackQuery,
    session: AsyncSession,
    service: WorkJournalService
):
    """Обработчик подтверждения выбранных исполнителей"""
    user_state = await service.get_user_state(callback.from_user.id)
    
    # Проверяем что есть выбранные исполнители
    selected_workers = []
    if user_state.draft_workers:
        try:
            import json
            selected_workers = json.loads(user_state.draft_workers)
        except (json.JSONDecodeError, TypeError):
            pass
    
    if not selected_workers:
        await callback.answer("Выберите хотя бы одного исполнителя!", show_alert=True)
        return
    
    # Переходим к подтверждению записи
    await service.set_user_state(
        callback.from_user.id,
        WorkJournalState.CONFIRMING_ENTRY
    )
    
    # Получаем обновленное состояние для отображения
    user_state = await service.get_user_state(callback.from_user.id)
    
    confirmation_text = format_draft_confirmation(user_state)
    
    await callback.message.edit_text(
        confirmation_text,
        reply_markup=create_confirmation_keyboard(),
        parse_mode="MarkdownV2"
    )
    
    workers_count = len(selected_workers)
    await callback.answer(f"Выбрано исполнителей: {workers_count}")


async def handle_single_worker_selection(
    callback: CallbackQuery,
    session: AsyncSession,
    service: WorkJournalService,
    worker: str
):
    """Обработчик одиночного выбора исполнителя (для совместимости)"""
    import json
    
    await service.set_user_state(
        callback.from_user.id,
        WorkJournalState.CONFIRMING_ENTRY,
        draft_workers=json.dumps([worker], ensure_ascii=False)
    )
    
    # Получаем обновленное состояние для отображения
    user_state = await service.get_user_state(callback.from_user.id)
    
    confirmation_text = format_draft_confirmation(user_state)
    
    await callback.message.edit_text(
        confirmation_text,
        reply_markup=create_confirmation_keyboard(),
        parse_mode="MarkdownV2"
    )
    
    await callback.answer(f"Выбран исполнитель: {worker}")


async def get_user_info(session: AsyncSession, telegram_user_id: int) -> Tuple[str, str]:
    """Получить информацию о пользователе"""
    
    result = await session.execute(
        select(BotUser).where(BotUser.telegram_user_id == telegram_user_id)
    )
    user = result.scalar_one_or_none()
    
    if user:
        user_name = user.first_name or user.username or f"User_{telegram_user_id}"
        user_email = f"{user.username}@example.com" if user.username else f"user_{telegram_user_id}@telegram.bot"
        return user_name, user_email
    
    return f"User_{telegram_user_id}", f"user_{telegram_user_id}@telegram.bot"
