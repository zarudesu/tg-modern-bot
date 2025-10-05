"""
Клавиатуры для модуля журнала работ
"""
from datetime import date, timedelta
from typing import List, Optional, Tuple
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ..utils.work_journal_constants import (
    CALLBACK_PREFIX, 
    CallbackAction, 
    EMOJI,
    DEFAULT_DURATIONS
)


def build_callback_data(action: CallbackAction, data: str = "") -> str:
    """Построить callback_data для кнопки"""
    if data:
        return f"{CALLBACK_PREFIX}:{action.value}:{data}"
    return f"{CALLBACK_PREFIX}:{action.value}"


def parse_callback_data(callback_data: str) -> Tuple[str, str]:
    """Разобрать callback_data"""
    parts = callback_data.split(":", 2)
    if len(parts) >= 2:
        action = parts[1]
        data = parts[2] if len(parts) > 2 else ""
        return action, data
    return "", ""


def create_date_selection_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора даты"""
    builder = InlineKeyboardBuilder()
    
    # Сегодня и вчера
    today = date.today()
    yesterday = today - timedelta(days=1)
    
    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['date']} Сегодня ({today.strftime('%d.%m')})",
            callback_data=build_callback_data(CallbackAction.SELECT_TODAY)
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['date']} Вчера ({yesterday.strftime('%d.%m')})",
            callback_data=build_callback_data(CallbackAction.SELECT_YESTERDAY)
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['date']} Другая дата",
            callback_data=build_callback_data(CallbackAction.SELECT_CUSTOM_DATE)
        )
    )
    
    # Навигация
    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['cross']} Отмена",
            callback_data=build_callback_data(CallbackAction.CANCEL)
        )
    )
    
    return builder.as_markup()


def create_company_selection_keyboard(companies: List[str]) -> InlineKeyboardMarkup:
    """Клавиатура для выбора компании"""
    builder = InlineKeyboardBuilder()
    
    # Добавляем кнопки для компаний (по 2 в ряд)
    for i in range(0, len(companies), 2):
        row_buttons = []
        for j in range(i, min(i + 2, len(companies))):
            company = companies[j]
            row_buttons.append(
                InlineKeyboardButton(
                    text=company,
                    callback_data=build_callback_data(CallbackAction.SELECT_COMPANY, company)
                )
            )
        builder.row(*row_buttons)
    
    # Добавить свою компанию
    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['add']} Другая компания",
            callback_data=build_callback_data(CallbackAction.ADD_CUSTOM_COMPANY)
        )
    )
    
    # Навигация
    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['back']} Назад",
            callback_data=build_callback_data(CallbackAction.BACK)
        ),
        InlineKeyboardButton(
            text=f"{EMOJI['cross']} Отмена",
            callback_data=build_callback_data(CallbackAction.CANCEL)
        )
    )
    
    return builder.as_markup()


def create_duration_selection_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора длительности работ"""
    builder = InlineKeyboardBuilder()
    
    # Добавляем кнопки для предустановленных длительностей (по 2 в ряд)
    for i in range(0, len(DEFAULT_DURATIONS), 2):
        row_buttons = []
        for j in range(i, min(i + 2, len(DEFAULT_DURATIONS))):
            duration = DEFAULT_DURATIONS[j]
            row_buttons.append(
                InlineKeyboardButton(
                    text=duration,
                    callback_data=build_callback_data(CallbackAction.SELECT_DURATION, duration)
                )
            )
        builder.row(*row_buttons)
    
    # Добавить свое время
    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['add']} Другое время",
            callback_data=build_callback_data(CallbackAction.ADD_CUSTOM_DURATION)
        )
    )
    
    # Навигация
    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['back']} Назад",
            callback_data=build_callback_data(CallbackAction.BACK)
        ),
        InlineKeyboardButton(
            text=f"{EMOJI['cross']} Отмена",
            callback_data=build_callback_data(CallbackAction.CANCEL)
        )
    )
    
    return builder.as_markup()


def create_travel_selection_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора типа работ (выезд/удаленно)"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['travel']} Да, был выезд",
            callback_data=build_callback_data(CallbackAction.SELECT_TRAVEL_YES)
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['remote']} Нет, удаленно",
            callback_data=build_callback_data(CallbackAction.SELECT_TRAVEL_NO)
        )
    )
    
    # Навигация
    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['back']} Назад",
            callback_data=build_callback_data(CallbackAction.BACK)
        ),
        InlineKeyboardButton(
            text=f"{EMOJI['cross']} Отмена",
            callback_data=build_callback_data(CallbackAction.CANCEL)
        )
    )
    
    return builder.as_markup()


def create_worker_selection_keyboard(workers: List[str], selected_workers: List[str] = None) -> InlineKeyboardMarkup:
    """Клавиатура для выбора исполнителей (множественный выбор)"""
    builder = InlineKeyboardBuilder()
    
    if selected_workers is None:
        selected_workers = []
    
    # Добавляем кнопки для исполнителей с индикацией выбора
    for worker in workers:
        is_selected = worker in selected_workers
        prefix = "✅ " if is_selected else ""
        
        builder.row(
            InlineKeyboardButton(
                text=f"{prefix}{EMOJI['worker']} {worker}",
                callback_data=build_callback_data(CallbackAction.TOGGLE_WORKER, worker)
            )
        )
    
    # Добавить своего исполнителя
    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['add']} Другой исполнитель",
            callback_data=build_callback_data(CallbackAction.ADD_CUSTOM_WORKER)
        )
    )
    
    # Подтвердить выбор (только если есть выбранные)
    if selected_workers:
        builder.row(
            InlineKeyboardButton(
                text=f"{EMOJI['check']} Подтвердить выбор ({len(selected_workers)})",
                callback_data=build_callback_data(CallbackAction.CONFIRM_WORKERS)
            )
        )
    
    # Навигация
    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['back']} Назад",
            callback_data=build_callback_data(CallbackAction.BACK)
        ),
        InlineKeyboardButton(
            text=f"{EMOJI['cross']} Отмена",
            callback_data=build_callback_data(CallbackAction.CANCEL)
        )
    )
    
    return builder.as_markup()


def create_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения записи"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['check']} Сохранить",
            callback_data=build_callback_data(CallbackAction.CONFIRM_SAVE)
        )
    )

    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['edit']} Редактировать",
            callback_data=build_callback_data(CallbackAction.EDIT_ENTRY)
        ),
        InlineKeyboardButton(
            text=f"{EMOJI['cross']} Отмена",
            callback_data=build_callback_data(CallbackAction.CANCEL)
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="show_main_menu"
        )
    )

    return builder.as_markup()


def create_description_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для ввода описания"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['back']} Назад",
            callback_data=build_callback_data(CallbackAction.BACK)
        ),
        InlineKeyboardButton(
            text=f"{EMOJI['cross']} Отмена",
            callback_data=build_callback_data(CallbackAction.CANCEL)
        )
    )
    
    return builder.as_markup()


def create_history_menu_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для меню истории"""
    builder = InlineKeyboardBuilder()
    
    # Период
    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['date']} Сегодня",
            callback_data=build_callback_data(CallbackAction.HISTORY_TODAY)
        ),
        InlineKeyboardButton(
            text=f"{EMOJI['date']} Вчера",
            callback_data=build_callback_data(CallbackAction.HISTORY_YESTERDAY)
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['date']} За неделю",
            callback_data=build_callback_data(CallbackAction.HISTORY_WEEK)
        ),
        InlineKeyboardButton(
            text=f"{EMOJI['date']} За месяц",
            callback_data=build_callback_data(CallbackAction.HISTORY_MONTH)
        )
    )
    
    # Фильтры
    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['company']} По компании",
            callback_data=build_callback_data(CallbackAction.FILTER_COMPANY)
        ),
        InlineKeyboardButton(
            text=f"{EMOJI['worker']} По исполнителю",
            callback_data=build_callback_data(CallbackAction.FILTER_WORKER)
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['travel']} Только выезды",
            callback_data=build_callback_data(CallbackAction.FILTER_TRAVEL)
        ),
        InlineKeyboardButton(
            text=f"{EMOJI['remote']} Только удаленка",
            callback_data=build_callback_data(CallbackAction.FILTER_REMOTE)
        )
    )
    
    # Кнопка "Назад"
    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['back']} Назад",
            callback_data="show_main_menu"
        )
    )
    
    return builder.as_markup()


def create_report_menu_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для меню отчетов"""
    builder = InlineKeyboardBuilder()
    
    # Стандартные отчеты
    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['date']} Дневной отчет",
            callback_data=build_callback_data(CallbackAction.REPORT_DAILY)
        ),
        InlineKeyboardButton(
            text=f"{EMOJI['date']} Недельный отчет",
            callback_data=build_callback_data(CallbackAction.REPORT_WEEKLY)
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['date']} Месячный отчет",
            callback_data=build_callback_data(CallbackAction.REPORT_MONTHLY)
        )
    )
    
    # Отчеты по группам
    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['worker']} По исполнителям",
            callback_data=build_callback_data(CallbackAction.REPORT_BY_WORKER)
        ),
        InlineKeyboardButton(
            text=f"{EMOJI['company']} По компаниям",
            callback_data=build_callback_data(CallbackAction.REPORT_BY_COMPANY)
        )
    )
    
    return builder.as_markup()


def create_back_cancel_keyboard() -> InlineKeyboardMarkup:
    """Простая клавиатура Назад/Отмена"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['back']} Назад",
            callback_data=build_callback_data(CallbackAction.BACK)
        ),
        InlineKeyboardButton(
            text=f"{EMOJI['cross']} Отмена",
            callback_data=build_callback_data(CallbackAction.CANCEL)
        )
    )
    
    return builder.as_markup()


def create_continue_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для продолжения"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['forward']} Продолжить",
            callback_data=build_callback_data(CallbackAction.CONTINUE)
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text=f"{EMOJI['edit']} Изменить дату",
            callback_data=build_callback_data(CallbackAction.SELECT_DATE)
        ),
        InlineKeyboardButton(
            text=f"{EMOJI['cross']} Отмена",
            callback_data=build_callback_data(CallbackAction.CANCEL)
        )
    )
    
    return builder.as_markup()


def create_description_input_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для ввода описания работ - просто Назад/Отмена"""
    return create_back_cancel_keyboard()
