"""
Константы и перечисления для модуля журнала работ
"""
from enum import Enum
from typing import List, Dict


class WorkJournalState(Enum):
    """Состояния заполнения журнала работ"""
    IDLE = "idle"
    SELECTING_DATE = "selecting_date"
    ENTERING_CUSTOM_DATE = "entering_custom_date"
    SELECTING_COMPANY = "selecting_company"
    ENTERING_CUSTOM_COMPANY = "entering_custom_company"
    SELECTING_DURATION = "selecting_duration"
    ENTERING_CUSTOM_DURATION = "entering_custom_duration"
    ENTERING_DESCRIPTION = "entering_description"
    SELECTING_TRAVEL = "selecting_travel"
    SELECTING_WORKER = "selecting_worker"
    ENTERING_CUSTOM_WORKER = "entering_custom_worker"
    CONFIRMING_ENTRY = "confirming_entry"


class N8nSyncStatus(Enum):
    """Статусы синхронизации с n8n"""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


# Предустановленные компании
DEFAULT_COMPANIES: List[str] = [
    "Харц Лабз",
    "3Д.РУ", 
    "Сад Здоровья",
    "Дельта",
    "Моисеев",
    "Стифтер",
    "Веха",
    "Сосновый бор",
    "Бибирево",
    "Ромашка",
    "Вёшки 95",
    "Вондига Парк",
    "Ива",
    "ЦифраЦифра"
]

# Предустановленные длительности работ
DEFAULT_DURATIONS: List[str] = [
    "5 мин",
    "10 мин", 
    "15 мин",
    "30 мин",
    "45 мин",
    "1 час",
    "1.5 часа",
    "2 часа"
]

# Предустановленные исполнители
DEFAULT_WORKERS: List[str] = [
    "Тимофей",
    "Дима",
    "Костя"
]

# Настройки для callback data
CALLBACK_PREFIX = "wj"  # work journal

# Коды действий для callback
class CallbackAction(Enum):
    """Действия для callback кнопок"""
    # Навигация
    CONTINUE = "continue"
    BACK = "back"
    CANCEL = "cancel"
    
    # Выбор данных
    SELECT_DATE = "sel_date"
    SELECT_TODAY = "today"
    SELECT_YESTERDAY = "yesterday"
    SELECT_CUSTOM_DATE = "custom_date"
    
    SELECT_COMPANY = "sel_comp"
    ADD_CUSTOM_COMPANY = "add_comp"
    
    SELECT_DURATION = "sel_dur"
    ADD_CUSTOM_DURATION = "add_dur"
    
    SELECT_TRAVEL_YES = "travel_yes"
    SELECT_TRAVEL_NO = "travel_no"
    
    SELECT_WORKER = "sel_work"
    ADD_CUSTOM_WORKER = "add_work" 
    TOGGLE_WORKER = "toggle_work"  # Переключить выбор исполнителя
    CONFIRM_WORKERS = "confirm_work"  # Подтвердить выбранных исполнителей
    
    # Подтверждение
    CONFIRM_SAVE = "confirm"
    EDIT_ENTRY = "edit"
    
    # Просмотр истории
    HISTORY_TODAY = "hist_today"
    HISTORY_YESTERDAY = "hist_yesterday"
    HISTORY_WEEK = "hist_week"
    HISTORY_MONTH = "hist_month"
    HISTORY_CUSTOM = "hist_custom"
    
    # Фильтры истории
    FILTER_COMPANY = "filt_comp"
    FILTER_WORKER = "filt_work"
    FILTER_TRAVEL = "filt_travel"
    FILTER_REMOTE = "filt_remote"
    
    # Отчеты
    REPORT_DAILY = "rep_daily"
    REPORT_WEEKLY = "rep_weekly"
    REPORT_MONTHLY = "rep_monthly"
    REPORT_BY_WORKER = "rep_worker"
    REPORT_BY_COMPANY = "rep_comp"


# Эмодзи для интерфейса
EMOJI = {
    "journal": "📋",
    "date": "📅",
    "company": "🏢", 
    "time": "⏱",
    "description": "📝",
    "travel": "🚗",
    "remote": "💻",
    "worker": "👤",
    "check": "✅",
    "cross": "❌",
    "edit": "✏️",
    "back": "⬅️",
    "forward": "➡️",
    "add": "➕",
    "search": "🔍",
    "report": "📊",
    "history": "📋",
    "stats": "📈"
}

# Форматы сообщений
MESSAGE_TEMPLATES = {
    "start_entry": f"{EMOJI['journal']} *Журнал работ*\n\nСоздание новой записи о выполненных работах\\.",
    "date_selection": f"{EMOJI['date']} *Выберите дату:*",
    "custom_date_prompt": f"{EMOJI['date']} *Введите дату*\n\nВведите дату в формате ДД\\.ММ\\.ГГГГ\n\nНапример: 08\\.08\\.2025",
    "company_selection": f"{EMOJI['company']} *Выберите компанию:*", 
    "custom_company_prompt": f"{EMOJI['company']} *Новая компания*\n\nВведите название новой компании:",
    "duration_selection": f"{EMOJI['time']} *Время на работу:*",
    "custom_duration_prompt": f"{EMOJI['time']} *Произвольное время*\n\nВведите время в разных форматах:\n\nНапример: 45 мин, 2 часа, 1\\.5 часа, 90 мин",
    "description_prompt": f"{EMOJI['description']} *Описание выполненных работ*\n\nНапишите подробное описание того, что было сделано:",
    "description_input": f"{EMOJI['description']} *Описание выполненных работ*\n\nНапишите подробное описание того, что было сделано:",
    "travel_selection": f"{EMOJI['travel']} *Был ли выезд на объект?*",
    "worker_selection": f"{EMOJI['worker']} *Кто выполнял работы?*",
    "confirmation": f"{EMOJI['check']} *Подтверждение записи*"
}
