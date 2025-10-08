"""
Обработчики текстового ввода для журнала работ

КРИТИЧЕСКИ ВАЖНО: Эти обработчики работают только при активных состояниях work_journal
Используют фильтр IsWorkJournalActiveFilter для изоляции от других модулей
"""

from aiogram import Router, F
from aiogram.types import Message
from datetime import date, datetime

from .filters import IsWorkJournalActiveFilter
from ...database.database import get_async_session
from ...services.work_journal_service import WorkJournalService
from ...utils.work_journal_constants import WorkJournalState, MESSAGE_TEMPLATES
from ...utils.work_journal_keyboards import (
    create_company_selection_keyboard,
    create_duration_selection_keyboard,
    create_description_input_keyboard,
    create_travel_selection_keyboard,
    create_confirmation_keyboard
)
from ...utils.work_journal_formatters import (
    escape_markdown_v2,
    format_draft_confirmation,
    format_error_message
)
from ...utils.logger import bot_logger

router = Router()


@router.message(F.text, IsWorkJournalActiveFilter())
async def handle_work_journal_text_input(message: Message):
    """
    ГЛАВНЫЙ обработчик текстового ввода для work_journal
    
    Работает ТОЛЬКО при активных состояниях:
    - НЕ idle
    - НЕ None
    - Любое другое активное состояние work_journal
    
    Этот фильтр обеспечивает изоляцию от других модулей
    """
    try:
        user_id = message.from_user.id
        text = message.text.strip()
        
        bot_logger.info(f"Work journal text input: '{text}' from user {user_id}")
        
        async for session in get_async_session():
            service = WorkJournalService(session)
            user_state = await service.get_user_state(user_id)
            
            if not user_state or not user_state.current_state:
                bot_logger.warning(f"No active work_journal state for user {user_id}")
                return
            
            current_state = user_state.current_state
            bot_logger.info(f"Processing work_journal state: {current_state} for user {user_id}")
            
            # Обработка в зависимости от состояния
            if current_state == WorkJournalState.ENTERING_CUSTOM_DATE.value:
                await handle_custom_date_input(message, session, service, text)
            
            elif current_state == WorkJournalState.ENTERING_CUSTOM_COMPANY.value:
                await handle_custom_company_input(message, session, service, text)
            
            elif current_state == WorkJournalState.ENTERING_CUSTOM_DURATION.value:
                await handle_custom_duration_input(message, session, service, text)
            
            elif current_state == WorkJournalState.ENTERING_DESCRIPTION.value:
                await handle_description_input(message, session, service, text)
            
            elif current_state == WorkJournalState.ENTERING_CUSTOM_WORKER.value:
                await handle_custom_worker_input(message, session, service, text)
            
            else:
                bot_logger.warning(f"Unknown work_journal state: {current_state} for user {user_id}")
                # Не показываем сообщение пользователю, просто игнорируем
                # (может быть state от другого модуля, например task_reports)
                return
            
    except Exception as e:
        bot_logger.error(f"Error in work_journal text handler for user {message.from_user.id}: {e}")
        await message.answer(
            format_error_message("general"),
            parse_mode="MarkdownV2"
        )


async def handle_custom_date_input(
    message: Message,
    session,
    service: WorkJournalService,
    text: str
):
    """Обработчик ввода кастомной даты"""
    try:
        user_id = message.from_user.id
        
        # Парсим дату в формате ДД.ММ.ГГГГ
        parsed_date = datetime.strptime(text, "%d.%m.%Y").date()
        
        # Валидация даты - разрешаем любые прошлые даты, ограничиваем только будущее
        today = date.today()
        max_date = date(today.year + 1, 12, 31)  # Максимум на год вперед
        
        if parsed_date > max_date:
            max_date_str = max_date.strftime('%d\\.%m\\.%Y')
            await message.answer(
                f"❌ *Слишком далекая дата*\n\nМаксимальная дата: {max_date_str}",
                parse_mode="MarkdownV2"
            )
            return
        
        # Сохраняем дату и переходим к выбору компании
        await service.set_user_state(
            user_id,
            WorkJournalState.SELECTING_COMPANY,
            draft_date=parsed_date
        )
        
        # Получаем список компаний
        companies = await service.get_companies()
        
        await message.answer(
            MESSAGE_TEMPLATES['company_selection'],
            reply_markup=create_company_selection_keyboard(companies),
            parse_mode="MarkdownV2"
        )
        
    except ValueError:
        today = date.today()
        today_str = today.strftime('%d\\.%m\\.%Y')
        await message.answer(
            f"❌ *Неверный формат даты*\n\nВведите дату в формате ДД\\.ММ\\.ГГГГ \\(например: {today_str}\\)",
            parse_mode="MarkdownV2"
        )


async def handle_custom_company_input(
    message: Message,
    session,
    service: WorkJournalService,
    text: str
):
    """Обработчик ввода кастомной компании"""
    user_id = message.from_user.id
    
    # Сохраняем новую компанию
    await service.add_company(text)
    
    await service.set_user_state(
        user_id,
        WorkJournalState.SELECTING_DURATION,
        draft_company=text
    )
    
    await message.answer(
        MESSAGE_TEMPLATES['duration_selection'],
        reply_markup=create_duration_selection_keyboard(),
        parse_mode="MarkdownV2"
    )


async def handle_custom_duration_input(
    message: Message,
    session,
    service: WorkJournalService,
    text: str
):
    """Обработчик ввода кастомного времени с валидацией"""
    user_id = message.from_user.id
    
    try:
        # Парсим время в разных форматах
        text_lower = text.lower().strip()
        duration_minutes = None
        
        # Попробуем разные форматы
        import re
        
        # Формат "2 часа", "1 час", "час"
        hour_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:ч|час|часа|часов|hours?)', text_lower)
        # Формат "30 мин", "минут"  
        min_match = re.search(r'(\d+)\s*(?:мин|минут|минута|minutes?)', text_lower)
        
        if hour_match and min_match:
            # Если есть и часы и минуты: "1 час 30 мин"
            hours = float(hour_match.group(1))
            minutes = int(min_match.group(1))
            duration_minutes = int(hours * 60) + minutes
        elif hour_match:
            # Только часы: "2.5 часа", "1 час"
            hours = float(hour_match.group(1))
            duration_minutes = int(hours * 60)
        elif min_match:
            # Только минуты: "45 мин"
            duration_minutes = int(min_match.group(1))
        else:
            # Пытаемся как чистое число (минуты)
            duration_minutes = int(text)
        
        # Валидация диапазона
        if duration_minutes <= 0:
            await message.answer(
                "❌ *Некорректное время*\n\nВремя должно быть больше 0 минут\\.",
                parse_mode="MarkdownV2"
            )
            return
        
        if duration_minutes > 1440:  # 24 часа
            await message.answer(
                "❌ *Слишком много времени*\n\nМаксимальное время: 1440 минут \\(24 часа\\)\\.",
                parse_mode="MarkdownV2"
            )
            return
        
        # Проверяем, нужно ли подтверждение (число <= 13 может быть часами)
        if text.isdigit() and int(text) <= 13:
            # Показываем подтверждение
            from ...utils.work_journal_keyboards import InlineKeyboardBuilder, InlineKeyboardButton, build_callback_data, CallbackAction
            
            builder = InlineKeyboardBuilder()
            
            # Опция: минуты
            builder.row(
                InlineKeyboardButton(
                    text=f"✅ {duration_minutes} минут",
                    callback_data=build_callback_data(CallbackAction.SELECT_DURATION, f"{duration_minutes} мин")
                )
            )
            
            # Опция: часы (если <= 13)
            if int(text) <= 13:
                hours_minutes = int(text) * 60
                hours_text = f"{text} ч" if int(text) == 1 else f"{text} ч"
                builder.row(
                    InlineKeyboardButton(
                        text=f"🕒 {hours_text} ({hours_minutes} мин)",
                        callback_data=build_callback_data(CallbackAction.SELECT_DURATION, hours_text)
                    )
                )
            
            # Кнопки навигации
            builder.row(
                InlineKeyboardButton(text="⬅️ Назад", callback_data=build_callback_data(CallbackAction.BACK)),
                InlineKeyboardButton(text="❌ Отмена", callback_data=build_callback_data(CallbackAction.CANCEL))
            )
            
            await message.answer(
                f"🤔 *Уточните время*\n\nВы ввели: **{text}**\n\nЧто вы имели в виду?",
                reply_markup=builder.as_markup(),
                parse_mode="MarkdownV2"
            )
            return
        
        # Форматируем время
        if duration_minutes < 60:
            formatted_duration = f"{duration_minutes} мин"
        else:
            hours = duration_minutes // 60
            minutes = duration_minutes % 60
            if minutes == 0:
                formatted_duration = f"{hours} ч"
            else:
                formatted_duration = f"{hours} ч {minutes} мин"
        
        await service.set_user_state(
            user_id,
            WorkJournalState.ENTERING_DESCRIPTION,
            draft_duration=formatted_duration
        )
        
        await message.answer(
            MESSAGE_TEMPLATES['description_input'],
            reply_markup=create_description_input_keyboard(),
            parse_mode="MarkdownV2"
        )
        
    except ValueError:
        await message.answer(
            "❌ *Неверный формат времени*\n\nВведите время в минутах \\(только число\\)\n\nПример: 60, 120, 180",
            parse_mode="MarkdownV2"
        )


async def handle_description_input(
    message: Message,
    session,
    service: WorkJournalService,
    text: str
):
    """Обработчик ввода описания работ"""
    user_id = message.from_user.id
    
    await service.set_user_state(
        user_id,
        WorkJournalState.SELECTING_TRAVEL,
        draft_description=text
    )
    
    await message.answer(
        MESSAGE_TEMPLATES['travel_selection'],
        reply_markup=create_travel_selection_keyboard(),
        parse_mode="MarkdownV2"
    )


async def handle_custom_worker_input(
    message: Message,
    session,
    service: WorkJournalService,
    text: str
):
    """Обработчик ввода кастомного исполнителя"""
    user_id = message.from_user.id
    
    # Сохраняем нового исполнителя
    await service.add_worker(text)
    
    # Получаем текущее состояние и добавляем нового исполнителя к выбранным
    user_state = await service.get_user_state(user_id)
    current_workers = user_state.draft_workers or []
    if text not in current_workers:
        current_workers.append(text)
    
    await service.set_user_state(
        user_id,
        WorkJournalState.CONFIRMING_ENTRY,
        draft_workers=current_workers
    )
    
    # Показываем финальное подтверждение
    user_state = await service.get_user_state(user_id)
    confirmation_text = format_draft_confirmation(user_state)
    
    await message.answer(
        confirmation_text,
        reply_markup=create_confirmation_keyboard(),
        parse_mode="MarkdownV2"
    )
