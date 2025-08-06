"""
Форматтеры для модуля журнала работ
"""
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional
from ..database.work_journal_models import WorkJournalEntry, UserWorkJournalState
from ..utils.work_journal_constants import EMOJI


def escape_markdown_v2(text: str) -> str:
    """Экранирование специальных символов для MarkdownV2"""
    # Символы, которые нужно экранировать в MarkdownV2
    chars_to_escape = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    for char in chars_to_escape:
        text = text.replace(char, f'\\{char}')
    
    return text


def format_date_for_display(date_obj: date) -> str:
    """Форматировать дату для отображения"""
    today = date.today()
    yesterday = today - timedelta(days=1)
    
    if date_obj == today:
        return f"{date_obj.strftime('%d.%m.%Y')} (сегодня)"
    elif date_obj == yesterday:
        return f"{date_obj.strftime('%d.%m.%Y')} (вчера)"
    else:
        return date_obj.strftime('%d.%m.%Y')


def format_work_entry_short(entry: WorkJournalEntry) -> str:
    """Краткое форматирование записи для списков"""
    date_str = format_date_for_display(entry.work_date)
    travel_icon = EMOJI['travel'] if entry.is_travel else EMOJI['remote']
    travel_text = "Выезд" if entry.is_travel else "Удаленно"
    
    # Обрезаем описание если слишком длинное
    description = entry.work_description
    if len(description) > 50:
        description = description[:47] + "..."
    
    # Парсим исполнителей из JSON
    try:
        import json
        workers = json.loads(entry.worker_names)
        workers_text = ", ".join(workers)
    except (json.JSONDecodeError, TypeError):
        workers_text = entry.worker_names or "Не указан"
    
    return (
        f"{EMOJI['date']} {escape_markdown_v2(date_str)} \\| "
        f"{EMOJI['company']} {escape_markdown_v2(entry.company)} \\| "
        f"{EMOJI['time']} {escape_markdown_v2(entry.work_duration)} \\| "
        f"{EMOJI['worker']} {escape_markdown_v2(workers_text)} \\| "
        f"{travel_icon} {travel_text}\n"
        f"{EMOJI['description']} {escape_markdown_v2(description)}\n"
        f"_Создал:_ {escape_markdown_v2(entry.created_by_name)}"
    )


def format_work_entry_detailed(entry: WorkJournalEntry) -> str:
    """Подробное форматирование записи"""
    date_str = format_date_for_display(entry.work_date)
    travel_text = "Да" if entry.is_travel else "Нет"
    
    # Парсим исполнителей из JSON
    try:
        import json
        workers = json.loads(entry.worker_names)
        workers_text = ", ".join(workers)
    except (json.JSONDecodeError, TypeError):
        workers_text = entry.worker_names or "Не указан"
    
    return (
        f"*{EMOJI['journal']} Запись в журнале работ*\n\n"
        f"{EMOJI['date']} *Дата:* {escape_markdown_v2(date_str)}\n"
        f"{EMOJI['company']} *Компания:* {escape_markdown_v2(entry.company)}\n"
        f"{EMOJI['time']} *Время:* {escape_markdown_v2(entry.work_duration)}\n"
        f"{EMOJI['worker']} *Исполнители:* {escape_markdown_v2(workers_text)}\n"
        f"{EMOJI['travel']} *Выезд:* {travel_text}\n\n"
        f"{EMOJI['description']} *Описание работ:*\n"
        f"{escape_markdown_v2(entry.work_description)}\n\n"
        f"_Создал:_ {escape_markdown_v2(entry.created_by_name)}\n"
        f"_Создано:_ {escape_markdown_v2(entry.created_at.strftime('%d.%m.%Y %H:%M'))}"
    )


def format_draft_confirmation(state: UserWorkJournalState) -> str:
    """Форматирование черновика для подтверждения"""
    date_str = format_date_for_display(state.draft_date) if state.draft_date else "Не выбрана"
    travel_text = "Да" if state.draft_is_travel else "Нет" if state.draft_is_travel is not None else "Не выбрано"
    
    # Парсим выбранных исполнителей
    workers_text = "Не выбраны"
    if state.draft_workers:
        try:
            import json
            workers = json.loads(state.draft_workers)
            workers_text = ", ".join(workers) if workers else "Не выбраны"
        except (json.JSONDecodeError, TypeError):
            workers_text = state.draft_workers
    
    return (
        f"*{EMOJI['check']} Подтверждение записи*\n\n"
        f"{EMOJI['date']} *Дата:* {escape_markdown_v2(date_str)}\n"
        f"{EMOJI['company']} *Компания:* {escape_markdown_v2(state.draft_company or 'Не выбрана')}\n"
        f"{EMOJI['time']} *Время:* {escape_markdown_v2(state.draft_duration or 'Не выбрано')}\n"
        f"{EMOJI['worker']} *Исполнители:* {escape_markdown_v2(workers_text)}\n"
        f"{EMOJI['travel']} *Выезд:* {travel_text}\n\n"
        f"{EMOJI['description']} *Описание работ:*\n"
        f"{escape_markdown_v2(state.draft_description or 'Не указано')}"
    )


def format_statistics_report(stats: Dict[str, Any], title: str = "Статистика работ") -> str:
    """Форматирование статистики"""
    if stats["total_entries"] == 0:
        return f"*{EMOJI['stats']} {title}*\n\nЗаписей не найдено\\."
    
    text = f"*{EMOJI['stats']} {title}*\n\n"
    
    # Общая статистика
    text += f"{EMOJI['journal']} *Всего записей:* {stats['total_entries']}\n"
    text += f"{EMOJI['travel']} *Выездов:* {stats['travel_count']} ({stats['travel_percentage']}%)\n"
    text += f"{EMOJI['remote']} *Удаленно:* {stats['remote_count']} ({stats['remote_percentage']}%)\n\n"
    
    # Период
    if stats["date_range"]:
        date_from = format_date_for_display(stats["date_range"]["from"])
        date_to = format_date_for_display(stats["date_range"]["to"])
        text += f"{EMOJI['date']} *Период:* {escape_markdown_v2(date_from)} \\- {escape_markdown_v2(date_to)}\n\n"
    
    # Топ исполнители
    if stats["workers"]:
        text += f"{EMOJI['worker']} *По исполнителям:*\n"
        for worker, count in list(stats["workers"].items())[:5]:  # Топ 5
            text += f"• {escape_markdown_v2(worker)}: {count} записи\n"
        text += "\n"
    
    # Топ компании
    if stats["companies"]:
        text += f"{EMOJI['company']} *Топ компании:*\n"
        for company, count in list(stats["companies"].items())[:5]:  # Топ 5
            text += f"• {escape_markdown_v2(company)}: {count} записи\n"
    
    return text


def format_entries_list(entries: List[WorkJournalEntry], title: str = "Записи работ") -> str:
    """Форматирование списка записей"""
    if not entries:
        return f"*{EMOJI['history']} {title}*\n\nЗаписей не найдено\\."
    
    text = f"*{EMOJI['history']} {title}*\n\n"
    text += f"Найдено записей: {len(entries)}\n\n"
    
    for i, entry in enumerate(entries[:10], 1):  # Показываем первые 10 записей
        text += f"*{i}\\. * {format_work_entry_short(entry)}\n\n"
    
    if len(entries) > 10:
        text += f"\\.\\.\\. и еще {len(entries) - 10} записей\\."
    
    return text


def format_help_message() -> str:
    """Форматирование справки по командам журнала работ"""
    return (
        f"*{EMOJI['journal']} Журнал работ \\- Справка*\n\n"
        f"*Основные команды:*\n"
        f"{EMOJI['add']} `/journal` \\- Создать новую запись\n"
        f"{EMOJI['history']} `/history` \\- Просмотр истории работ\n"
        f"{EMOJI['report']} `/report` \\- Отчеты и статистика\n\n"
        f"*Фильтры истории:*\n"
        f"• По дате \\(сегодня, вчера, неделя, месяц\\)\n"
        f"• По компании\n"
        f"• По исполнителю\n"
        f"• По типу работ \\(выезд/удаленно\\)\n\n"
        f"*Отчеты:*\n"
        f"• Дневные, недельные, месячные\n"
        f"• По исполнителям и компаниям\n"
        f"• Сводная статистика\n\n"
        f"_Все данные автоматически сохраняются в Google Sheets\\._"
    )


def format_error_message(error_type: str = "general") -> str:
    """Форматирование сообщений об ошибках"""
    error_messages = {
        "general": f"{EMOJI['cross']} Произошла ошибка\\. Попробуйте позже\\.",
        "network": f"{EMOJI['cross']} Ошибка сети\\. Проверьте подключение\\.",
        "validation": f"{EMOJI['cross']} Некорректные данные\\. Проверьте ввод\\.",
        "permission": f"{EMOJI['cross']} Недостаточно прав для выполнения действия\\.",
        "not_found": f"{EMOJI['cross']} Запись не найдена\\.",
        "timeout": f"{EMOJI['cross']} Время ожидания истекло\\. Попробуйте снова\\."
    }
    
    return error_messages.get(error_type, error_messages["general"])


def format_success_message(action: str = "general") -> str:
    """Форматирование сообщений об успехе"""
    success_messages = {
        "created": f"{EMOJI['check']} Запись успешно создана и отправлена в Google Sheets\\!",
        "updated": f"{EMOJI['check']} Запись успешно обновлена\\!",
        "deleted": f"{EMOJI['check']} Запись успешно удалена\\!",
        "synced": f"{EMOJI['check']} Данные успешно синхронизированы\\!",
        "general": f"{EMOJI['check']} Операция выполнена успешно\\!"
    }
    
    return success_messages.get(action, success_messages["general"])


def format_company_list(companies: List[str]) -> str:
    """Форматирование списка компаний"""
    if not companies:
        return "Компании не настроены"
    
    text = "Доступные компании:\n"
    for i, company in enumerate(companies, 1):
        text += f"{i}. {company}\n"
    
    return text


def format_worker_list(workers: List[str]) -> str:
    """Форматирование списка исполнителей"""
    if not workers:
        return "Исполнители не настроены"
    
    text = "Доступные исполнители:\n"
    for i, worker in enumerate(workers, 1):
        text += f"{i}. {worker}\n"
    
    return text
