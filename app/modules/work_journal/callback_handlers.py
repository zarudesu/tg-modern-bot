"""
Обработчики callback кнопок для журнала работ - ПОЛНАЯ ВОССТАНОВЛЕННАЯ ВЕРСИЯ
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from datetime import date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from ...database.database import get_async_session
from ...services.work_journal_service import WorkJournalService
from ...utils.work_journal_constants import (
    WorkJournalState, 
    CallbackAction, 
    MESSAGE_TEMPLATES
)
from ...utils.work_journal_keyboards import (
    parse_callback_data,
    create_date_selection_keyboard,
    create_company_selection_keyboard,
    create_duration_selection_keyboard,
    create_travel_selection_keyboard,
    create_worker_selection_keyboard,
    create_confirmation_keyboard,
    create_description_keyboard,
    create_description_input_keyboard,
    create_continue_keyboard,
    create_history_menu_keyboard,
    create_report_menu_keyboard,
    create_back_cancel_keyboard,
    build_callback_data
)
from ...utils.work_journal_formatters import (
    format_date_for_display,
    format_draft_confirmation,
    format_error_message,
    format_success_message
)
from ...utils.logger import bot_logger

router = Router()


@router.callback_query(F.data.startswith("wj:"))
async def handle_journal_callback(callback: CallbackQuery):
    """Обработчик callback-запросов журнала работ"""
    try:
        user_id = callback.from_user.id
        action, data = parse_callback_data(callback.data)
        bot_logger.info(f"📋 Callback action: '{action}', data: '{data}' (expecting toggle_work={CallbackAction.TOGGLE_WORKER.value})")
        
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
            
            elif action == CallbackAction.SELECT_CUSTOM_DATE.value:
                await handle_custom_date_request(callback, session, service)
            
            elif action == CallbackAction.SELECT_DATE.value:
                await handle_return_to_date_selection(callback, session, service)
            
            elif action == CallbackAction.SELECT_COMPANY.value:
                await handle_company_selection(callback, session, service, data)
            
            elif action == CallbackAction.ADD_CUSTOM_COMPANY.value:
                await handle_custom_company_request(callback, session, service)
            
            elif action == CallbackAction.SELECT_DURATION.value:
                await handle_duration_selection(callback, session, service, data)
            
            elif action == CallbackAction.ADD_CUSTOM_DURATION.value:
                await handle_custom_duration_request(callback, session, service)
            
            elif action == CallbackAction.SELECT_TRAVEL_YES.value:
                await handle_travel_selection(callback, session, service, True)
            
            elif action == CallbackAction.SELECT_TRAVEL_NO.value:
                await handle_travel_selection(callback, session, service, False)
            
            elif action == CallbackAction.TOGGLE_WORKER.value:
                bot_logger.info(f"🔧 TOGGLE_WORKER action: data='{data}' for user {user_id}")
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
    
    elif user_state.current_state == WorkJournalState.ENTERING_DESCRIPTION.value:
        # Если пользователь нажал "Далее" без ввода описания, просим ввести текст
        if not user_state.draft_description:
            await callback.answer("Сначала введите описание работ!", show_alert=True)
            return
        
        # Переходим к выбору типа работ (выезд/удаленно)
        await service.set_user_state(
            callback.from_user.id,
            WorkJournalState.SELECTING_TRAVEL
        )
        
        await callback.message.edit_text(
            MESSAGE_TEMPLATES['travel_selection'],
            reply_markup=create_travel_selection_keyboard(),
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
        MESSAGE_TEMPLATES['description_input'],
        reply_markup=create_description_input_keyboard(),
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
        reply_markup=create_worker_selection_keyboard(workers),
        parse_mode="MarkdownV2"
    )
    
    travel_type = "Выезд к клиенту" if is_travel else "Удаленная работа"
    await callback.answer(f"Выбрано: {travel_type}")


async def handle_toggle_worker(
    callback: CallbackQuery,
    session: AsyncSession,
    service: WorkJournalService,
    worker_name: str
):
    """Обработчик переключения исполнителя"""
    user_state = await service.get_user_state(callback.from_user.id)
    
    if not user_state:
        await callback.answer("Сессия истекла", show_alert=True)
        return
        
    # Получаем текущий список выбранных исполнителей через новый метод
    current_workers = user_state.get_draft_workers() if hasattr(user_state, 'get_draft_workers') else []
    
    # Создаем новый список
    new_workers_list = list(current_workers)
    
    if worker_name in new_workers_list:
        # Убираем исполнителя из списка
        new_workers_list.remove(worker_name)
    else:
        # Добавляем исполнителя в список
        new_workers_list.append(worker_name)
    
    # Обновляем состояние через сервис (там есть правильная сериализация)
    await service.set_user_state(
        callback.from_user.id,
        WorkJournalState.SELECTING_WORKER,
        draft_workers=new_workers_list
    )
    
    # Обновляем клавиатуру
    workers = await service.get_workers()
    
    try:
        await callback.message.edit_reply_markup(
            reply_markup=create_worker_selection_keyboard(workers, selected_workers=new_workers_list)
        )
    except Exception as e:
        # Игнорируем ошибку "message is not modified"
        if "message is not modified" not in str(e):
            raise e
    
    action = "добавлен" if worker_name in new_workers_list else "убран"
    await callback.answer(f"Исполнитель {worker_name} {action}")


async def handle_confirm_workers(
    callback: CallbackQuery,
    session: AsyncSession,
    service: WorkJournalService
):
    """Обработчик подтверждения выбора исполнителей"""
    user_state = await service.get_user_state(callback.from_user.id)
    
    # Проверяем через новый метод
    selected_workers = user_state.get_draft_workers() if (user_state and hasattr(user_state, 'get_draft_workers')) else []
    
    if not user_state or not selected_workers:
        await callback.answer("Выберите хотя бы одного исполнителя", show_alert=True)
        return
    
    # Переходим к финальному подтверждению
    await service.set_user_state(
        callback.from_user.id,
        WorkJournalState.CONFIRMING_ENTRY
    )
    
    # Формируем текст подтверждения
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
    worker_name: str
):
    """Обработчик одиночного выбора исполнителя (для обратной совместимости)"""
    await service.set_user_state(
        callback.from_user.id,
        WorkJournalState.CONFIRMING_ENTRY,
        draft_workers=[worker_name]
    )
    
    user_state = await service.get_user_state(callback.from_user.id)
    confirmation_text = format_draft_confirmation(user_state)
    
    await callback.message.edit_text(
        confirmation_text,
        reply_markup=create_confirmation_keyboard(),
        parse_mode="MarkdownV2"
    )
    
    await callback.answer(f"Выбран исполнитель: {worker_name}")


async def handle_confirm_save(
    callback: CallbackQuery,
    session: AsyncSession,
    service: WorkJournalService,
    user_state
):
    """Обработчик сохранения записи"""
    try:
        # Сохраняем запись из draft состояния
        user_state = await service.get_user_state(callback.from_user.id)
        if not user_state:
            raise Exception("User state not found")
            
        # Получаем информацию о создателе записи
        from ...database.models import BotUser
        from sqlalchemy import select
        import json
        
        result = await session.execute(
            select(BotUser).where(BotUser.telegram_user_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            creator_name = f"@{user.username}" if user.username else (user.first_name or f"User_{callback.from_user.id}")
            user_email = f"{user.username}@example.com" if user.username else f"user_{callback.from_user.id}@telegram.bot"
        else:
            creator_name = f"User_{callback.from_user.id}"
            user_email = f"user_{callback.from_user.id}@telegram.bot"
        
        # Парсим worker_names из JSON
        try:
            worker_names = json.loads(user_state.draft_workers) if user_state.draft_workers else []
            if not worker_names:
                await callback.answer("Выберите хотя бы одного исполнителя!", show_alert=True)
                return
        except (json.JSONDecodeError, TypeError):
            await callback.answer("Ошибка в данных исполнителей!", show_alert=True)
            return
        
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
        
        if entry:
            # Очищаем состояние пользователя
            await service.clear_user_state(callback.from_user.id)
            
            # Отправляем данные в n8n
            try:
                from ...services.n8n_integration_service import N8nIntegrationService
                
                user_data = {
                    "first_name": user.first_name if user else callback.from_user.first_name,
                    "username": user.username if user else callback.from_user.username
                }
                
                n8n_service = N8nIntegrationService()
                bot_logger.info(f"Attempting to send entry {entry.id} to n8n with webhook URL: {n8n_service.webhook_url}")
                success = await n8n_service.send_with_retry(entry, user_data, session)
                if success:
                    bot_logger.info(f"✅ Successfully sent entry {entry.id} to n8n")
                else:
                    bot_logger.error(f"❌ Failed to send entry {entry.id} to n8n after retries")
                
            except Exception as e:
                bot_logger.error(f"Error sending to n8n for entry {entry.id}: {e}")
                # Не прерываем процесс, так как запись уже сохранена в БД
            
            # Отправляем уведомления с упоминаниями в групповой чат
            try:
                from ...services.worker_mention_service import WorkerMentionService
                from ...config import settings
                
                # Проверяем что групповой чат настроен
                if settings.work_journal_group_chat_id:
                    bot_logger.info(f"Attempting to send group notification for entry {entry.id} to chat {settings.work_journal_group_chat_id}")
                    mention_service = WorkerMentionService(session, callback.bot)
                    
                    # Отправляем уведомления только в групповой чат с упоминаниями
                    success, errors = await mention_service.send_work_assignment_notifications(
                        entry, creator_name, settings.work_journal_group_chat_id
                    )
                    
                    if success:
                        bot_logger.info(f"✅ Successfully sent group notification for entry {entry.id}")
                    
                    if errors:
                        for error in errors[:2]:  # Показываем только первые 2 ошибки
                            bot_logger.warning(f"Group mention notification error: {error}")
                else:
                    bot_logger.warning("WORK_JOURNAL_GROUP_CHAT_ID not configured - skipping group notification")
                            
            except Exception as e:
                bot_logger.error(f"Error sending group mention notifications: {e}")
                # Не прерываем процесс, так как основная задача выполнена
            
            success_text = format_success_message(entry)

            # Добавляем кнопку "В главное меню"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 В главное меню", callback_data="start_menu")]
            ])

            await callback.message.edit_text(
                success_text,
                reply_markup=keyboard,
                parse_mode="MarkdownV2"
            )
            
            await callback.answer("Запись успешно сохранена!")
        else:
            await callback.message.edit_text(
                format_error_message("save"),
                parse_mode="MarkdownV2"
            )
            await callback.answer("Ошибка сохранения", show_alert=True)
            
    except Exception as e:
        bot_logger.error(f"Error saving entry for user {callback.from_user.id}: {e}")
        await callback.message.edit_text(
            format_error_message("general"),
            parse_mode="MarkdownV2"
        )
        await callback.answer("Произошла ошибка", show_alert=True)


async def handle_cancel_action(
    callback: CallbackQuery,
    session: AsyncSession,
    service: WorkJournalService
):
    """Обработчик отмены"""
    await service.clear_user_state(callback.from_user.id)
    
    await callback.message.edit_text(
        "❌ *Создание записи отменено*\n\nДля нового создания записи используйте команду `/journal`",
        parse_mode="MarkdownV2"
    )
    
    await callback.answer("Отменено")


async def handle_back_action(
    callback: CallbackQuery,
    session: AsyncSession,
    service: WorkJournalService,
    user_state
):
    """Обработчик возврата на предыдущий шаг"""
    current_state = WorkJournalState(user_state.current_state)
    
    if current_state == WorkJournalState.SELECTING_COMPANY:
        # Возврат к выбору даты
        await service.set_user_state(
            callback.from_user.id,
            WorkJournalState.SELECTING_DATE,
            draft_date=user_state.draft_date
        )
        
        await callback.message.edit_text(
            f"{MESSAGE_TEMPLATES['start_entry']}\n\n📅 Выберите дату работ:",
            reply_markup=create_date_selection_keyboard(),
            parse_mode="MarkdownV2"
        )
        
    elif current_state == WorkJournalState.SELECTING_DURATION:
        # Возврат к выбору компании
        await service.set_user_state(
            callback.from_user.id,
            WorkJournalState.SELECTING_COMPANY,
            draft_company=user_state.draft_company
        )
        
        companies = await service.get_companies()
        
        await callback.message.edit_text(
            MESSAGE_TEMPLATES['company_selection'],
            reply_markup=create_company_selection_keyboard(companies),
            parse_mode="MarkdownV2"
        )
        
    elif current_state == WorkJournalState.ENTERING_CUSTOM_DURATION:
        # Возврат к выбору длительности  
        await service.set_user_state(
            callback.from_user.id,
            WorkJournalState.SELECTING_DURATION,
            draft_duration=user_state.draft_duration
        )
        
        await callback.message.edit_text(
            MESSAGE_TEMPLATES['duration_selection'],
            reply_markup=create_duration_selection_keyboard(),
            parse_mode="MarkdownV2"
        )
        
    elif current_state == WorkJournalState.ENTERING_DESCRIPTION:
        # Возврат к выбору длительности
        await service.set_user_state(
            callback.from_user.id,
            WorkJournalState.SELECTING_DURATION,
            draft_duration=user_state.draft_duration
        )
        
        await callback.message.edit_text(
            MESSAGE_TEMPLATES['duration_selection'],
            reply_markup=create_duration_selection_keyboard(),
            parse_mode="MarkdownV2"
        )
        
    elif current_state == WorkJournalState.SELECTING_TRAVEL:
        # Возврат к вводу описания
        await service.set_user_state(
            callback.from_user.id,
            WorkJournalState.ENTERING_DESCRIPTION,
            draft_description=user_state.draft_description
        )
        
        await callback.message.edit_text(
            MESSAGE_TEMPLATES['description_prompt'],
            reply_markup=create_description_keyboard(),
            parse_mode="MarkdownV2"
        )
        
    elif current_state == WorkJournalState.SELECTING_WORKER:
        # Возврат к выбору типа работ
        await service.set_user_state(
            callback.from_user.id,
            WorkJournalState.SELECTING_TRAVEL,
            draft_is_travel=user_state.draft_is_travel
        )
        
        await callback.message.edit_text(
            MESSAGE_TEMPLATES['travel_selection'],
            reply_markup=create_travel_selection_keyboard(),
            parse_mode="MarkdownV2"
        )
        
    elif current_state == WorkJournalState.CONFIRMING_ENTRY:
        # Возврат к выбору исполнителей
        # Получаем список работников через новый метод
        current_workers = user_state.get_draft_workers() if hasattr(user_state, 'get_draft_workers') else []
        
        await service.set_user_state(
            callback.from_user.id,
            WorkJournalState.SELECTING_WORKER,
            draft_workers=current_workers
        )
        
        workers = await service.get_workers()
        
        await callback.message.edit_text(
            MESSAGE_TEMPLATES['worker_selection'],
            reply_markup=create_worker_selection_keyboard(workers, selected_workers=current_workers),
            parse_mode="MarkdownV2"
        )
    
    await callback.answer("Возврат к предыдущему шагу")


async def handle_custom_date_request(
    callback: CallbackQuery,
    session: AsyncSession,
    service: WorkJournalService
):
    """Обработчик запроса ввода произвольной даты"""
    await service.set_user_state(
        callback.from_user.id,
        WorkJournalState.ENTERING_CUSTOM_DATE
    )
    
    await callback.message.edit_text(
        MESSAGE_TEMPLATES['custom_date_prompt'],
        reply_markup=create_back_cancel_keyboard(),
        parse_mode="MarkdownV2"
    )
    
    await callback.answer("Введите дату в формате дд.мм.гггг")


async def handle_return_to_date_selection(
    callback: CallbackQuery,
    session: AsyncSession,
    service: WorkJournalService
):
    """Обработчик возврата к выбору даты"""
    await service.set_user_state(
        callback.from_user.id,
        WorkJournalState.SELECTING_DATE
    )
    
    await callback.message.edit_text(
        f"{MESSAGE_TEMPLATES['start_entry']}\n\n📅 Выберите дату работ:",
        reply_markup=create_date_selection_keyboard(),
        parse_mode="MarkdownV2"
    )
    
    await callback.answer("Выбор даты")


async def handle_custom_company_request(
    callback: CallbackQuery,
    session: AsyncSession,
    service: WorkJournalService
):
    """Обработчик запроса ввода новой компании"""
    await service.set_user_state(
        callback.from_user.id,
        WorkJournalState.ENTERING_CUSTOM_COMPANY
    )
    
    await callback.message.edit_text(
        MESSAGE_TEMPLATES['custom_company_prompt'],
        reply_markup=create_back_cancel_keyboard(),
        parse_mode="MarkdownV2"
    )
    
    await callback.answer("Введите название новой компании")


async def handle_custom_duration_request(
    callback: CallbackQuery,
    session: AsyncSession,
    service: WorkJournalService
):
    """Обработчик запроса ввода произвольной длительности"""
    await service.set_user_state(
        callback.from_user.id,
        WorkJournalState.ENTERING_CUSTOM_DURATION
    )
    
    await callback.message.edit_text(
        MESSAGE_TEMPLATES['custom_duration_prompt'],
        reply_markup=create_back_cancel_keyboard(),
        parse_mode="MarkdownV2"
    )
    
    await callback.answer("Введите время в минутах")


# Дополнительные callback обработчики для совместимости с главным меню
@router.callback_query(F.data == "start_journal")
async def callback_start_journal_from_menu(callback: CallbackQuery):
    """Запуск journal из главного меню"""
    try:
        await callback.answer("📋 Открываю журнал работ...")
        
        # Имитируем команду /journal
        user_id = callback.from_user.id
        
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
            
            await callback.message.edit_text(
                start_text,
                reply_markup=create_date_selection_keyboard(),
                parse_mode="MarkdownV2"
            )
            
    except Exception as e:
        bot_logger.error(f"Error in start_journal callback: {e}")
        await callback.answer("Ошибка открытия журнала")


@router.callback_query(F.data == "show_history")
async def callback_show_history_from_menu(callback: CallbackQuery):
    """Показать историю из главного меню"""
    try:
        await callback.answer("📊 Загружаю историю...")
        
        # Имитируем команду /history - переадресация
        await callback.message.edit_text(
            "📊 *История работ*\n\nИспользуйте команду `/history` для просмотра истории работ\\.",
            parse_mode="MarkdownV2"
        )
        
    except Exception as e:
        bot_logger.error(f"Error in show_history callback: {e}")
        await callback.answer("Ошибка загрузки истории")


@router.callback_query(F.data == "show_reports")
async def callback_show_reports_from_menu(callback: CallbackQuery):
    """Показать отчеты из главного меню"""
    try:
        await callback.answer("📈 Генерирую отчеты...")
        
        # Имитируем команду /report - переадресация
        await callback.message.edit_text(
            "📈 *Отчеты по работам*\n\nИспользуйте команду `/report` для создания отчетов\\.",
            parse_mode="MarkdownV2"
        )
        
    except Exception as e:
        bot_logger.error(f"Error in show_reports callback: {e}")
        await callback.answer("Ошибка генерации отчетов")


@router.callback_query(F.data == "manage_companies")
async def callback_manage_companies_from_menu(callback: CallbackQuery):
    """Управление компаниями из главного меню"""
    try:
        await callback.answer("🏢 Загружаю управление компаниями...")
        
        # Имитируем команду /companies - переадресация
        await callback.message.edit_text(
            "🏢 *Управление компаниями*\n\nИспользуйте команду `/companies` для управления компаниями\\.",
            parse_mode="MarkdownV2"
        )
        
    except Exception as e:
        bot_logger.error(f"Error in manage_companies callback: {e}")
        await callback.answer("Ошибка управления компаниями")
