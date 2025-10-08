# Task Reports Module Refactoring Plan

**Дата:** 2025-10-08  
**Цель:** Разбить большие файлы task_reports модуля на меньшие, исправить баги, улучшить читаемость

---

## 📊 Текущее состояние

### Размеры файлов
```
app/modules/task_reports/
├── metadata_handlers.py    1188 строк ❌ ОЧЕНЬ БОЛЬШОЙ
├── handlers.py              941 строка  ❌ БОЛЬШОЙ
├── keyboards.py             262 строки  ✅ OK
├── router.py                 19 строк   ✅ OK
├── states.py                 27 строк   ✅ OK
└── __init__.py               17 строк   ✅ OK

app/services/
└── task_reports_service.py  891 строка  ⚠️ ТЕРПИМО
```

### Текущие баги (5 штук)

| # | Проблема | Файл | Приоритет |
|---|----------|------|-----------|
| 1 | Autofill не заполняет report_text | task_reports_service.py:272-293 | 🔴 HIGH |
| 2 | Edit mode сбрасывает все поля | metadata_handlers.py:1074-1170 | 🔴 HIGH |
| 3 | HarzLabs вместо "Харц Лабз" | metadata_handlers.py:398,524 | 🟡 MEDIUM |
| 4 | Markdown ошибка в group notification | worker_mention_service.py:76-92 | 🔴 HIGH |
| 5 | Google Sheets URL неправильный | .env:19 | 🟢 LOW |

---

## 🎯 Целевая структура

\`\`\`
app/modules/task_reports/
├── handlers/
│   ├── __init__.py
│   ├── creation.py         # Создание TaskReport
│   ├── preview.py          # Просмотр списка/отчёта
│   ├── approval.py         # Approve/reject
│   └── edit.py             # Редактирование
│
├── metadata/
│   ├── __init__.py
│   ├── duration.py         # Duration selection
│   ├── company.py          # Company selection
│   ├── workers.py          # Workers selection
│   ├── travel.py           # Travel type
│   └── client.py           # Client contact
│
├── utils.py                # Company mapping, форматирование
├── keyboards.py            # Как есть
├── states.py               # Как есть
└── router.py               # Обновить импорты
\`\`\`

---

## 📋 Чеклист выполнения

### Этап 0: Подготовка (30 мин)
- [x] Создать TASK_REPORTS_REFACTORING.md
- [ ] Создать CURRENT_BUGS.md
- [ ] Git commit текущего состояния
- [ ] Создать ветку refactor/task-reports-module

### Этап 1: Структура (15 мин)
- [ ] Создать папки handlers/, metadata/
- [ ] Создать __init__.py файлы

### Этап 2: Metadata handlers (1 час)
- [ ] duration.py
- [ ] company.py + company mapping (БАГ #3)
- [ ] workers.py + autofill check (БАГ #1)
- [ ] travel.py
- [ ] client.py

### Этап 3: Main handlers (45 мин)
- [ ] creation.py
- [ ] preview.py + autofill check
- [ ] approval.py + Markdown fix (БАГ #4)
- [ ] edit.py + preserve metadata (БАГ #2)

### Этап 4: Utils (30 мин)
- [ ] utils.py с COMPANY_MAPPING
- [ ] escape_markdown_v2
- [ ] format_report_preview

### Этап 5: Router (15 мин)
- [ ] router.py с правильным порядком

### Этап 6: Баги (1 час)
- [ ] БАГ #1: Autofill
- [ ] БАГ #2: Edit mode
- [ ] БАГ #3: Company mapping
- [ ] БАГ #4: Markdown error
- [ ] БАГ #5: Google Sheets URL

### Этап 7: Тестирование (30 мин)
- [ ] Full flow test
- [ ] Edit mode test
- [ ] Company mapping test

---

## ⏱ Оценка времени

**Итого:** ~4-5 часов

---

## 📚 Для продолжения в новом чате

Прочитайте эти файлы:
1. docs/TASK_REPORTS_REFACTORING.md (этот файл)
2. docs/CURRENT_BUGS.md
3. app/modules/task_reports/router.py
4. app/modules/task_reports/states.py

Затем выполняйте чеклист поэтапно.
