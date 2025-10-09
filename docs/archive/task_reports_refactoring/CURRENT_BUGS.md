# Task Reports Module - Current Bugs

**Дата:** 2025-10-08
**Статус:** В разработке (рефакторинг)

---

## БАГ #1: Autofill не заполняет report_text 🔴 HIGH

### Описание
При создании TaskReport через webhook, report_text остаётся пустым, хотя в Plane есть title, description и comments.

### Воспроизведение
1. Plane task с описанием и комментами → перевести в Done
2. Webhook создаёт TaskReport
3. Admin заполняет metadata (duration → company → workers)
4. Preview показывает: "⚠️ Отчёт не заполнен"

### Файлы
- `app/services/task_reports_service.py:272-293` - функция `fetch_and_generate_report_from_plane`
- `app/services/task_reports_service.py:299-418` - функция `_generate_report_text`

### Текущие логи
```
✅ Retrieved 1 comments for ce47ac5c-e480-4e3f-9822-6f1334dbcf36
```
НО нет логов "Auto-generated report" или "No content"

### Гипотеза проблемы
1. `_generate_report_text` возвращает пустую строку
2. Причина: строка 392-393 проверяет `len(report_lines) <= 2`
3. Если есть только header + title, возвращает ""
4. Комментарии пропускаются если `comment_html` пустой (строка 340-341)

### Решение
```python
# В _generate_report_text:
for comment in comments:
    comment_html = comment.get('comment_html', '').strip()
    comment_text = comment.get('comment', '').strip()  # ADD fallback
    
    if not comment_html and not comment_text:  # FIX
        continue
    
    # Use whichever is available
    text_to_parse = comment_html or comment_text
```

### Тест
```python
# Проверить что report_text заполнен
task_report = await service.get_task_report(session, 24)
assert task_report.report_text is not None
assert len(task_report.report_text) > 100
```

---

## БАГ #2: Edit mode сбрасывает все поля 🔴 HIGH

### Описание
Когда admin нажимает "Редактировать" и меняет одно поле (например description), бот заставляет заполнить ВСЕ поля заново (duration, company, workers, travel).

### Воспроизведение
1. Открыть TaskReport в preview
2. Нажать "Редактировать"
3. Выбрать "Описание"
4. Ввести новое описание
5. Бот просит выбрать duration → company → workers → travel (всё заново)

### Файлы
- `app/modules/task_reports/metadata_handlers.py:1074-1188` - `callback_edit_field`

### Проблема в коде
```python
# Строка 1094
await state.set_state(TaskReportStates.filling_report)
# Устанавливает state, но НЕ сохраняет existing metadata
```

### Решение
```python
async def callback_edit_field(callback: CallbackQuery, state: FSMContext):
    # Load existing TaskReport
    task_report = await service.get_task_report(session, task_report_id)
    
    # Save existing metadata to state
    existing_data = {
        "task_report_id": task_report_id,
        "duration": task_report.work_duration,
        "company": task_report.company,
        "workers": task_report.worker_names,
        "travel": task_report.is_travel,
        "editing_mode": True,  # Flag to skip metadata steps
        "editing_field": field_name  # Which field we're editing
    }
    await state.update_data(**existing_data)
    
    # Set appropriate state
    await state.set_state(TaskReportStates.filling_report)
    
    # После ввода нового значения - сразу вернуться в preview
```

### Тест
```python
# Edit только description
original_duration = task_report.work_duration
original_company = task_report.company

# User edits description
await callback_edit_field(...)
await text_report_input(message, state)  # Новое описание

# Проверить что остальные поля не сбросились
task_report = await service.get_task_report(session, task_report_id)
assert task_report.work_duration == original_duration
assert task_report.company == original_company
```

---

## БАГ #3: HarzLabs вместо "Харц Лабз" 🟡 MEDIUM

### Описание
При выборе company из Plane проекта "HarzLabs", в Google Sheets попадает "HarzLabs" вместо русского "Харц Лабз".

### Воспроизведение
1. TaskReport от Plane проекта "HarzLabs"
2. Company auto-selected: "HarzLabs"
3. Approve → WorkJournalEntry создан
4. Google Sheets: компания = "HarzLabs" ❌

### Файлы
- `app/modules/task_reports/metadata_handlers.py:398` - `callback_company`
- `app/modules/task_reports/metadata_handlers.py:524` - `text_custom_company`
- `app/utils/work_journal_constants.py:32-47` - список компаний

### Проблема
Нет маппинга между Plane названиями и нашими русскими названиями.

### Решение
Создать `app/modules/task_reports/utils.py`:

```python
# Company name mapping: Plane → наши названия
COMPANY_MAPPING = {
    "HarzLabs": "Харц Лабз",
    "3D.RU": "3Д.РУ",
    "Garden of Health": "Сад Здоровья",
    "Delta": "Дельта",
    "Moiseev": "Моисеев",
    "Stifter": "Стифтер",
    "Vekha": "Веха",
    "Sosnovy Bor": "Сосновый бор",
    "Bibirevo": "Бибирево",
    "Romashka": "Ромашка",
    "Vyoshki 95": "Вёшки 95",
    "Vondiga Park": "Вондига Парк",
    "Iva": "Ива",
    "CifraCifra": "ЦифраЦифра"
}

def map_company_name(plane_name: str) -> str:
    """Map Plane company name to our internal Russian name"""
    return COMPANY_MAPPING.get(plane_name, plane_name)
```

Использовать в `callback_company`:
```python
from ..utils import map_company_name

selected_company = parts[2]
mapped_company = map_company_name(selected_company)
await state.update_data(company=mapped_company)
```

### Тест
```python
# Plane project "HarzLabs"
task_report = await service.create_task_report_from_webhook(...)
assert task_report.plane_project_name == "HarzLabs"

# После выбора company
await callback_company(...)
state_data = await state.get_data()
assert state_data["company"] == "Харц Лабз"  # Mapped!
```

---

## БАГ #4: Markdown ошибка в group notification 🔴 HIGH

### Описание
При approve TaskReport и создании WorkJournalEntry, group notification падает с ошибкой Markdown parsing: "Can't find end of entity starting at byte offset 436"

### Лог ошибки
```
ERROR | app.services.worker_mention_service:send_work_assignment_notifications:130 | 
Failed to send chat notification: Telegram server says - Bad Request: 
can't parse entities: Can't find end of the entity starting at byte offset 436
```

### Файлы
- `app/services/worker_mention_service.py:76-92` - `format_work_assignment_message`
- `app/services/worker_mention_service.py:120-130` - `send_work_assignment_notifications`

### Проблема
Markdown MarkdownV2 требует экранирования специальных символов: `_*[]()~>#+-=|{}.!`

Текущий код:
```python
message = (
    f"📋 **Новая запись в журнале работ**\n\n"
    f"👥 **Исполнители:** {workers_text}\n"  # НЕ экранировано!
    f"🏢 **Компания:** {entry.company}\n"    # НЕ экранировано!
    f"📝 **Описание:**\n{entry.work_description}\n"  # НЕ экранировано!
)
```

### Решение
Добавить функцию экранирования:

```python
def escape_markdown_v2(text: str) -> str:
    """Escape special characters for MarkdownV2"""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

# Использовать:
workers_escaped = escape_markdown_v2(workers_text)
company_escaped = escape_markdown_v2(entry.company)
description_escaped = escape_markdown_v2(entry.work_description)

message = (
    f"📋 **Новая запись в журнале работ**\\n\\n"
    f"👥 **Исполнители:** {workers_escaped}\\n"
    f"🏢 **Компания:** {company_escaped}\\n"
    # ...
)
```

### Тест
```python
# Описание с спецсимволами
entry = WorkJournalEntry(
    company="Test & Co.",
    work_description="Fixed #123: error in task (urgent!)",
    # ...
)

# Отправить notification
success, errors = await service.send_work_assignment_notifications(...)
assert success == True
assert len(errors) == 0
```

---

## БАГ #5: Google Sheets URL неправильный 🟢 LOW

### Описание
Пользователь сообщает что ссылка на Google Sheets неправильная (пропущен символ подчёркивания в ID).

### Файлы
- `.env:19` - `GOOGLE_SHEETS_URL`

### Текущее значение
```
GOOGLE_SHEETS_URL=https://docs.google.com/spreadsheets/d/1jq3mnVWyGxSUG7FkzNF8EI77lYOJXXBTXDHxTJdWk/edit
```

### Действие
Проверить с пользователем правильный URL и обновить.

### Тест
Открыть URL в браузере, убедиться что таблица доступна.

---

## Приоритизация

1. **БАГ #1** 🔴 - Основной функционал (autofill)
2. **БАГ #4** 🔴 - Блокирует notifications
3. **БАГ #2** 🔴 - UX проблема (заставляет переделывать)
4. **БАГ #3** 🟡 - Данные некорректны но не критично
5. **БАГ #5** 🟢 - Просто проверка конфигурации

---

**Версия:** 1.0
**Последнее обновление:** 2025-10-08 17:35
