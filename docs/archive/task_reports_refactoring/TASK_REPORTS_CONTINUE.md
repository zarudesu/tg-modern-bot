# Task Reports - Продолжение работы (после контекста)

## 🔥 КРИТИЧЕСКИЕ ПРОБЛЕМЫ (нужно исправить СЕЙЧАС)

### 1. ❌ Комментарии не показываются в отчёте

**Проблема:** Функция `_generate_report_text` в `app/services/task_reports_service.py:344` ищет неправильный ключ.

**Текущий код (НЕПРАВИЛЬНО):**
```python
comment_text = comment.get('comment', '').strip()
```

**Исправление:**
Plane API использует ключ `comment_html`, не `comment`. Нужно изменить на:

```python
comment_text = comment.get('comment_html', '').strip()
```

**Файл:** `app/services/task_reports_service.py:344`

**Проверка после исправления:**
- Комментарии должны отображаться в уведомлении
- В preview должны быть видны комментарии под "Выполненные работы:"

---

### 2. ❌ Исполнители из Plane не выбраны автоматически

**Проблема:** В `handlers.py` мы загружаем `plane_assignees` в FSM state, но в `metadata_handlers.py` при показе клавиатуры workers они не выбраны по умолчанию.

**Где исправить:**
`app/modules/task_reports/metadata_handlers.py` - функция показа workers keyboard

**Что сделать:**
1. При первом показе клавиатуры workers проверить FSM state
2. Если `selected_workers` пусто, автоматически добавить `plane_assignees`
3. Показать их с галочками ✅

**Код:**
```python
# В callback который показывает workers keyboard первый раз
state_data = await state.get_data()
selected_workers = state_data.get("selected_workers", [])
plane_assignees = state_data.get("plane_assignees", [])

# Автовыбор исполнителей из Plane при первом показе
if not selected_workers and plane_assignees:
    selected_workers = plane_assignees.copy()
    await state.update_data(selected_workers=selected_workers)
```

---

### 3. ❌ После одобрения нет интеграции с Google Sheets

**Проблема:** В `callback_approve_only` (`app/modules/task_reports/handlers.py:666`) после одобрения отчёт просто сохраняется в БД, но НЕ отправляется:
1. В Google Sheets (как в work_journal)
2. Уведомление в чат
3. Кнопка "Главное меню"

**Что нужно сделать:**

#### A. Создать work_journal entry

После одобрения нужно создать запись в work_journal:

```python
from ..services import work_journal_service
from datetime import datetime

# Parse workers JSON
workers_list = []
if task_report.workers:
    workers_list = json.loads(task_report.workers)

# Create work journal entry
wj_service = work_journal_service.WorkJournalService(session)
entry = await wj_service.create_entry(
    telegram_user_id=callback.from_user.id,
    date=task_report.closed_at.date() if task_report.closed_at else datetime.now().date(),
    company=task_report.company,
    duration=task_report.work_duration,
    description=task_report.report_text,
    is_travel=task_report.is_travel,
    workers=",".join(workers_list) if workers_list else None
)

# Link to task report
task_report.work_journal_entry_id = entry.id
await session.commit()
```

#### B. Отправить в Google Sheets

```python
from ..integrations.google_sheets import sync_work_journal_entry

# Send to Google Sheets via n8n
await sync_work_journal_entry(entry)
```

#### C. Добавить кнопку "Главное меню"

```python
from ..utils.keyboards import main_menu_keyboard

await callback.message.edit_text(
    f"✅ Отчёт одобрен!\n\n"
    f"Задача #{task_report.plane_sequence_id} завершена.\n"
    f"Отчёт сохранён в базе данных и отправлен в Google Sheets.",
    parse_mode="Markdown",
    reply_markup=main_menu_keyboard()
)
```

**Файл:** `app/modules/task_reports/handlers.py` - функция `callback_approve_only`

---

### 4. ❌ "Автоматически заполнено" показывается когда пусто

**Проблема:** В уведомлении показывается "✅ Автоматически заполнено из work journal", но текст пустой.

**Где:** `app/webhooks/server.py` - формирование уведомления

**Исправление:**
```python
# Формируем сообщение
autofill_notice = ""
if task_report.auto_filled_from_journal and task_report.report_text:
    # Проверяем что report_text НЕ пустой
    if len(task_report.report_text.strip()) > 100:  # Минимальная длина
        autofill_notice = "\n\n✅ _Отчёт сгенерирован из комментариев Plane_"
```

---

## 📋 ПОЛНЫЙ CHECKLIST ДЛЯ СЛЕДУЮЩЕГО ЧАТА

### Шаг 1: Исправить комментарии (5 мин)
- [ ] Изменить `comment.get('comment')` → `comment.get('comment_html')`
- [ ] Пересобрать бота
- [ ] Создать тестовую задачу с комментариями
- [ ] Проверить что комментарии показываются

### Шаг 2: Автовыбор исполнителей (10 мин)
- [ ] Добавить автовыбор `plane_assignees` при первом показе workers
- [ ] Пересобрать
- [ ] Проверить что Костя выбран автоматически

### Шаг 3: Google Sheets интеграция (20 мин)
- [ ] Добавить создание work_journal entry после одобрения
- [ ] Добавить отправку в Google Sheets
- [ ] Добавить кнопку "Главное меню"
- [ ] Пересобрать
- [ ] Протестировать весь flow end-to-end

### Шаг 4: Полировка (10 мин)
- [ ] Исправить сообщение "автоматически заполнено"
- [ ] Добавить кнопки "Назад к началу" при отмене (pending todo)
- [ ] Финальное тестирование

---

## 🔧 БЫСТРЫЕ КОМАНДЫ

```bash
# Пересобрать бота
docker-compose -f docker-compose.bot.yml up -d --build

# Посмотреть логи
docker-compose -f docker-compose.bot.yml logs --tail=100 -f

# Проверить что комментарии загружаются
docker-compose -f docker-compose.bot.yml logs | grep "Retrieved.*comments"
```

---

## 📁 ФАЙЛЫ ДЛЯ РЕДАКТИРОВАНИЯ

### Критические:
1. `app/services/task_reports_service.py:344` - исправить ключ комментария
2. `app/modules/task_reports/metadata_handlers.py` - автовыбор workers
3. `app/modules/task_reports/handlers.py:666` - интеграция Google Sheets

### Опциональные:
4. `app/webhooks/server.py` - сообщение "автоматически заполнено"

---

## 🎯 ОЖИДАЕМЫЙ РЕЗУЛЬТАТ

После всех исправлений workflow должен быть:

1. **Задача Done в Plane** → webhook
2. **Уведомление админу** с комментариями и автовыбранными исполнителями
3. **Заполнение метаданных** через кнопки
4. **Одобрение** → создание work_journal entry → отправка в Google Sheets
5. **Финальное сообщение** с кнопкой "Главное меню"

---

## 💡 ПОДСКАЗКИ

### Plane API Structure (комментарии)

```json
{
  "comment_html": "<p>Текст комментария</p>",
  "actor_detail": {
    "display_name": "Константин Макейкин",
    "first_name": "Konstantin",
    "email": "zarudesu@gmail.com"
  },
  "created_at": "2025-10-08T12:00:00Z"
}
```

### Work Journal Service Usage

```python
from ..services import work_journal_service

wj_service = work_journal_service.WorkJournalService(session)
entry = await wj_service.create_entry(
    telegram_user_id=user_id,
    date=date_obj,
    company="Company Name",
    duration="2h",
    description="Work description",
    is_travel=False,
    workers="Worker1,Worker2"
)
```

---

## 🚨 ВАЖНО

- **НЕ** меняй структуру кода, только исправляй указанные проблемы
- **ВСЕГДА** тестируй после каждого исправления
- **ЛОГИРУЙ** все для отладки: `bot_logger.info(f"Debug: {variable}")`
