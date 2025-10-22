# Task Reports - Все исправления

## 🆕 Последние исправления (2025-10-22)

### 7. ✅ project_identifier всегда NULL для всех проектов

**Проблема**: Все task_reports имели `project_identifier = NULL`, из-за чего отчеты показывали "HHIVP-123" вместо "HARZL-94", "DELTA-30" и т.д.

**Корневая причина**: `PlaneProjectsManager.get_projects()` не извлекал поле `identifier` из Plane API response → все PlaneProject объекты имели `identifier=None`

**Файлы**:
- `app/integrations/plane/projects.py:39` - добавлено `identifier=project_data.get('identifier')`

**Исправление**:
```python
project = PlaneProject(
    id=project_data.get('id', ''),
    name=project_data.get('name', 'Unknown'),
    identifier=project_data.get('identifier'),  # HARZL, HHIVP, DELTA, etc.
    description=project_data.get('description'),
    workspace=project_data.get('workspace', ''),
    created_at=project_data.get('created_at'),
    updated_at=project_data.get('updated_at')
)
```

**Результат**: Теперь для НОВЫХ отчетов автоматически заполняется правильный project_identifier

**Commit**: `980cc4d` - "🐛 Fix: Add missing identifier field when fetching Plane projects"

---

### 8. ✅ Миграция 006 не была идемпотентной

**Проблема**: Миграция `006_add_project_identifier` использовала `op.add_column()`, что вызывало ошибку при повторном запуске (например, при пересборке Docker)

**Корневая причина**:
- Код был запущен на проде неделю назад
- Миграция не была применена
- Колонка была добавлена вручную
- При пересборке миграция пыталась добавить колонку повторно → ошибка

**Файлы**:
- `alembic/versions/006_add_project_identifier_to_task_reports.py`

**Исправление**:
```python
def upgrade():
    # Add project_identifier column to task_reports (idempotent)
    # Use raw SQL with IF NOT EXISTS for safety
    from sqlalchemy import text
    connection = op.get_bind()
    connection.execute(text("""
        ALTER TABLE task_reports
        ADD COLUMN IF NOT EXISTS project_identifier VARCHAR(20);
    """))

    # Add comment if column exists
    connection.execute(text("""
        COMMENT ON COLUMN task_reports.project_identifier IS 'Префикс проекта (HARZL, HHIVP, и т.д.)';
    """))
```

**Результат**: Миграция теперь безопасна для повторного запуска

**Commit**: `53d7df8` - "🔧 Fix: Make migration 006 idempotent (IF NOT EXISTS)"

---

### 9. ✅ SSH ключ для production сервера

**Проблема**: Каждое подключение к production требовало пароль `sshpass -p '...'`, что небезопасно и расходует токены

**Решение**: Настроен SSH ключ для беспарольного доступа

**Команды**:
```bash
# Создан RSA ключ 4096 бит
ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N "" -C "claude-code@tg-bot"

# Добавлен на production сервер
ssh-copy-id -i ~/.ssh/id_rsa.pub hhivp@rd.hhivp.com
```

**Результат**: Теперь можно подключаться без пароля: `ssh hhivp@rd.hhivp.com`

---

### 10. ✅ Исправлены имена исполнителей в work_journal

**Проблема**: В отчетах о работе показывались неправильные имена исполнителей ("D. Gusev", "Дима" вместо "dima_gusev", "Тимофей" вместо "timofey_batyrev")

**Корневая причина**:
- Таблица `work_journal_workers` была пустая → использовался DEFAULT_WORKERS hardcoded массив
- Админ выбирал display names из UI → они сохранялись в БД
- `map_workers_to_display_names_list()` ожидала telegram_usernames, получала display names → маппинг не работал

**Исправления**:
1. Заполнена `work_journal_workers` на проде (Костя, Дима, Тимофей с telegram_username)
2. Добавлен "D. Gusev" и варианты в PLANE_TO_TELEGRAM_MAP (`app/services/task_reports_service.py:66-85`)
3. Добавлен метод `get_workers_full()` в WorkJournalService

**Файлы**:
- `app/services/task_reports_service.py` - PLANE_TO_TELEGRAM_MAP
- `app/services/work_journal_service.py` - get_workers_full()
- Production DB - заполнена work_journal_workers

**Commit**: См. коммит с фиксом имен работников

---

## Список проблем из тестирования

1. ❌ **Одобрить думало но не сработало** - н8н/Google Sheets не синхронизируется
2. ❌ **Unknown автор** - не показывается имя автора комментария
3. ❌ **Описание задачи теряется** - не показывается в отчете
4. ❌ **Задача #20 вместо HHVIP-XX** - неправильный номер задачи
5. ❌ **Длительность в формате "2h"** - должно быть по-русски как в work_journal
6. ❌ **Ошибка при выборе типа работы** - `invalid literal for int() with base 10: 'None'`
7. ✅ **Главное меню не работает** - ИСПРАВЛЕНО (изменили callback_data на start_menu)
8. ✅ **project_identifier всегда NULL** - ИСПРАВЛЕНО (2025-10-22)
9. ✅ **Миграция не идемпотентна** - ИСПРАВЛЕНО (2025-10-22)
10. ✅ **Имена исполнителей неправильные** - ИСПРАВЛЕНО (2025-10-22)

---

## 1. Исправление: Company = NULL при одобрении

**Проблема**: При одобрении отчета `company` не указывается, что вызывает ошибку БД.

**Файл**: `app/modules/task_reports/handlers.py`

**Строка**: ~691

**Исправление**:
```python
# После получения task_report (строка ~683), нужно проверить что все поля заполнены:
if not task_report.company:
    await callback.answer("❌ Компания не указана", show_alert=True)
    return

if not task_report.work_duration:
    await callback.answer("❌ Длительность не указана", show_alert=True)
    return
```

---

## 2. Исправление: `invalid literal for int()`

**Проблема**: Ошибка при парсинге `report_id` из callback_data, когда он = "None"

**Файлы**: Все обработчики в `metadata_handlers.py` и `handlers.py`

**Причина**: `callback_data` содержит строку "None" вместо числа

**Исправление**:
Во всех обработчиках которые парсят report_id добавить проверку:

```python
# Вместо:
report_id = int(callback.data.split(":")[1])

# Использовать:
try:
    report_id_str = callback.data.split(":")[1]
    if report_id_str == "None" or not report_id_str:
        bot_logger.error(f"Invalid report_id in callback_data: {callback.data}")
        await callback.answer("❌ Неверный ID отчёта", show_alert=True)
        return
    report_id = int(report_id_str)
except (IndexError, ValueError) as e:
    bot_logger.error(f"Error parsing report_id from {callback.data}: {e}")
    await callback.answer("❌ Ошибка обработки", show_alert=True)
    return
```

**Обработчики которые нужно исправить**:
- `callback_work_type` (metadata_handlers.py:278)
- `callback_back_to_duration` (metadata_handlers.py:856)
- `callback_cancel_report` (handlers.py:456)
- Все остальные callback handlers которые используют report_id

---

## 3. Исправление: Номер задачи (#20 вместо HHIVP-XX)

**Проблема**: Показывается `task_report.id` (внутренний ID БД) вместо `task_report.plane_sequence_id` (номер из Plane)

**Файл**: `app/services/task_reports_service.py`

**Функция**: `generate_preview_text()`

**Строка**: ~200-250

**Исправление**:
```python
# Найти все места где используется:
f"Задача: #{task_report.id}"

# Заменить на:
f"Задача: #{task_report.plane_sequence_id}"
```

**Также проверить в**:
- `handlers.py` - уведомления админу
- `metadata_handlers.py` - предпросмотр
- Везде где отображается номер задачи

---

## 4. Исправление: Описание задачи исчезает

**Проблема**: Описание задачи (`task_report.task_description`) не показывается в финальном отчете

**Файл**: `app/services/task_reports_service.py`

**Функция**: `generate_preview_text()` и `_generate_report_text()`

**Проверить**:
1. Правильно ли сохраняется `task_description` при создании TaskReport
2. Правильно ли отображается в preview
3. Правильно ли отображается в финальном отчете

**Исправление**:
```python
# В _generate_report_text() убедиться что task_description включено:
text_parts = [
    f"📋 Отчёт по задаче {task_report.plane_identifier}\n",
    f"Задача: {task_report.task_name}\n",
]

# Добавить описание если есть:
if task_report.task_description:
    text_parts.append(f"\nОписание:\n{task_report.task_description}\n")

# Добавить комментарии:
if comments:
    text_parts.append("\nВыполненные работы:\n")
    for idx, comment in enumerate(comments, 1):
        # ...
```

---

## 5. Исправление: Формат длительности (2h → 2 часа)

**Проблема**: Используется английский формат "2h", "4h" вместо русского "2 часа", "4 часа"

**Решение**: Полностью переписать duration input по аналогии с work_journal

**Файл**: `app/modules/task_reports/metadata_handlers.py`

**Функция**: `callback_work_duration_input()`

### Изменения:

#### A. Клавиатура с предустановленными вариантами (как в work_journal)

```python
DEFAULT_DURATIONS = [
    "5 мин",
    "10 мин",
    "15 мин",
    "30 мин",
    "45 мин",
    "1 час",
    "1.5 часа",
    "2 часа"
]

def create_duration_keyboard(report_id: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора длительности (русский формат)"""
    builder = InlineKeyboardBuilder()

    # Добавляем кнопки для предустановленных длительностей (по 2 в ряд)
    for i in range(0, len(DEFAULT_DURATIONS), 2):
        row_buttons = []
        for j in range(i, min(i + 2, len(DEFAULT_DURATIONS))):
            duration = DEFAULT_DURATIONS[j]
            row_buttons.append(
                InlineKeyboardButton(
                    text=duration,
                    callback_data=f"tr_duration:{report_id}:{duration}"
                )
            )
        builder.row(*row_buttons)

    # Добавить свое время
    builder.row(
        InlineKeyboardButton(
            text="➕ Другое время",
            callback_data=f"tr_custom_duration:{report_id}"
        )
    )

    # Навигация
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data=f"tr_back_to_company:{report_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"tr_cancel:{report_id}")
    )

    return builder.as_markup()
```

#### B. Обработчик выбора duration из кнопок

```python
@router.callback_query(F.data.startswith("tr_duration:"))
async def callback_select_duration(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора длительности из предустановленных"""
    try:
        _, report_id_str, duration = callback.data.split(":", 2)
        report_id = int(report_id_str)

        async for session in get_async_session():
            service = TaskReportsService(session)
            await service.update_task_report(report_id, work_duration=duration)

            # Переход к выбору типа работы
            await callback.message.edit_text(
                "🚗 *Был ли выезд к клиенту?*",
                reply_markup=create_work_type_keyboard(report_id),
                parse_mode="Markdown"
            )
            await callback.answer()

    except Exception as e:
        bot_logger.error(f"Error selecting duration: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)
```

#### C. Обработчик кастомного ввода времени

```python
@router.callback_query(F.data.startswith("tr_custom_duration:"))
async def callback_custom_duration_input(callback: CallbackQuery, state: FSMContext):
    """Запрос на ввод кастомной длительности"""
    _, report_id_str = callback.data.split(":")
    report_id = int(report_id_str)

    await state.update_data(report_id=report_id, awaiting_custom_duration=True)
    await state.set_state(TaskReportStates.entering_duration)

    await callback.message.edit_text(
        "⏱️ *Введите длительность работы*\n\n"
        "Примеры:\n"
        "• `2 часа`\n"
        "• `1.5 часа`\n"
        "• `30 мин`\n"
        "• `1 час 30 мин`\n\n"
        "Формат: количество + единица измерения",
        reply_markup=create_cancel_keyboard(report_id),
        parse_mode="Markdown"
    )
    await callback.answer()
```

#### D. Text handler для кастомного ввода (как в work_journal)

```python
@router.message(TaskReportStates.entering_duration)
async def handle_custom_duration_text(message: Message, state: FSMContext):
    """Обработчик текстового ввода длительности"""
    try:
        text = message.text.strip()
        data = await state.get_data()
        report_id = data.get("report_id")

        if not report_id:
            await message.answer("❌ Ошибка: отчёт не найден")
            return

        # Парсим время (как в work_journal/text_handlers.py:167-286)
        import re

        text_lower = text.lower()
        duration_minutes = None

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
            try:
                duration_minutes = int(text)
            except ValueError:
                await message.answer(
                    "❌ *Неверный формат времени*\n\n"
                    "Введите время в формате:\n"
                    "• `2 часа`\n"
                    "• `30 мин`\n"
                    "• `1 час 30 мин`",
                    parse_mode="Markdown"
                )
                return

        # Валидация диапазона
        if duration_minutes <= 0:
            await message.answer("❌ Время должно быть больше 0 минут")
            return

        if duration_minutes > 1440:  # 24 часа
            await message.answer("❌ Максимальное время: 1440 минут (24 часа)")
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

        # Сохраняем
        async for session in get_async_session():
            service = TaskReportsService(session)
            await service.update_task_report(report_id, work_duration=formatted_duration)

            await state.clear()

            # Переход к выбору типа работы
            await message.answer(
                "🚗 *Был ли выезд к клиенту?*",
                reply_markup=create_work_type_keyboard(report_id),
                parse_mode="Markdown"
            )

    except Exception as e:
        bot_logger.error(f"Error handling custom duration: {e}")
        await message.answer("❌ Ошибка обработки")
```

---

## 6. Исправление: Unknown автор комментария

**Проблема**: Показывается "Unknown" вместо имени автора

**Файл**: `app/services/task_reports_service.py`

**Функция**: `_generate_report_text()`

**Строка**: ~350-360

**Текущий код**:
```python
actor_name = (
    actor_detail.get('display_name') or
    actor_detail.get('first_name') or
    'Unknown'
)
```

**Проверить Plane API структуру**:
Нужно посмотреть реальную структуру comment'ов из Plane API.

**Возможные варианты**:
- `actor_detail.display_name`
- `actor_detail.first_name` + `actor_detail.last_name`
- `actor` (вместо `actor_detail`)
- `created_by.display_name`

**Решение**: Логировать полную структуру комментария:
```python
bot_logger.info(f"Comment structure: {json.dumps(comment, indent=2)}")
```

Затем найти правильный путь к имени автора.

---

## Приоритет исправлений

1. **КРИТИЧНО**: #2 - `invalid literal for int()` (блокирует весь workflow)
2. **КРИТИЧНО**: #1 - Company = NULL (блокирует одобрение)
3. **ВЫСОКИЙ**: #5 - Формат длительности (UX проблема)
4. **СРЕДНИЙ**: #3 - Номер задачи (визуальная проблема)
5. **СРЕДНИЙ**: #4 - Описание задачи (информационная проблема)
6. **НИЗКИЙ**: #6 - Unknown автор (нужно изучить Plane API)

---

## План действий

1. Исправить #2 (report_id parsing) - добавить try/except везде
2. Исправить #1 (company validation) - добавить проверку перед созданием work_journal entry
3. Исправить #5 (duration format) - переписать по аналогии с work_journal
4. Исправить #3 (task number) - заменить id на plane_sequence_id
5. Исправить #4 (description) - проверить что сохраняется и отображается
6. Исследовать #6 (author name) - логировать структуру Plane API

После каждого исправления - пересобрать бота и тестировать.
