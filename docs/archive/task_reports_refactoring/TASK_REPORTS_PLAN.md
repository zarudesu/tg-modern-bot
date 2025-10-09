# 📋 Task Reports System - План разработки

## 🎯 Цель системы

**Автоматизация отчётности по выполненным заявкам клиентов**

Когда задача в Plane переводится в статус "Done":
1. ✅ Система автоматически создаёт TaskReport
2. 📝 Админ заполняет отчёт (что было сделано)
3. 👀 Админ проверяет и одобряет
4. 📤 Клиент получает отчёт в чат
5. ⏰ Система спамит напоминаниями если админ не заполнил

---

## 🏗️ Архитектура

### Компоненты системы:

```
┌─────────────┐
│   Plane.so  │ Task → Done
└──────┬──────┘
       │ webhook
       ▼
┌─────────────┐
│     n8n     │ Обрабатывает webhook, фильтрует события
└──────┬──────┘
       │ HTTP POST
       ▼
┌─────────────┐
│   Bot API   │ /webhooks/task-completed
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  TaskReport │ Создаётся в БД (status=pending)
│   Service   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Send Form  │ Админу отправляется форма
│  to Admin   │ "Требуется отчёт!"
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Admin fills │ FSM: waiting_for_report
│   Report    │ Админ пишет текст отчёта
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Review    │ FSM: reviewing_report
│  & Approve  │ Админ проверяет превью
└──────┬──────┘
       │
       ▼
┌─────────────┐
│Send to Client│ Отчёт отправляется в чат
│   in Chat   │ (reply на исходное сообщение)
└─────────────┘

       ПАРАЛЛЕЛЬНО:
┌─────────────┐
│  Reminder   │ Каждые 30 мин проверяет
│   Service   │ pending отчёты и спамит админу
└─────────────┘
```

---

## 📊 Структура БД

### TaskReport (новая таблица)

```sql
CREATE TABLE task_reports (
    id SERIAL PRIMARY KEY,

    -- Связь с заявкой
    support_request_id INT REFERENCES support_requests(id),

    -- Plane задача
    plane_issue_id VARCHAR(255) UNIQUE NOT NULL,
    plane_sequence_id INT,
    plane_project_id VARCHAR(255),
    task_title VARCHAR(500),
    task_description TEXT,

    -- Кто закрыл
    closed_by_plane_name VARCHAR(255),
    closed_by_telegram_username VARCHAR(255),
    closed_by_telegram_id BIGINT,
    closed_at TIMESTAMPTZ,

    -- Отчёт
    report_text TEXT,
    report_submitted_by BIGINT,
    report_submitted_at TIMESTAMPTZ,

    -- Интеграция с Work Journal
    work_journal_entry_id INT REFERENCES work_journal_entries(id),
    auto_filled_from_journal BOOLEAN DEFAULT FALSE,

    -- Статус: pending → draft → approved → sent_to_client
    status VARCHAR(50) DEFAULT 'pending',

    -- Напоминания
    reminder_count INT DEFAULT 0,
    last_reminder_at TIMESTAMPTZ,
    reminder_level INT DEFAULT 0,

    -- Клиент
    client_chat_id BIGINT,
    client_user_id BIGINT,
    client_message_id BIGINT,
    client_notified_at TIMESTAMPTZ,

    -- Метаданные
    webhook_payload TEXT,
    error_message TEXT,
    notes TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Индексы:**
- `idx_task_reports_status` - быстрый поиск по статусу
- `idx_task_reports_pending` - pending отчёты конкретного админа
- `idx_task_reports_reminders` - для системы напоминаний
- `idx_task_reports_client` - история отчётов клиента

---

## 📁 Файловая структура

```
app/
├── database/
│   ├── task_reports_models.py          ✅ ГОТОВО (TaskReport model)
│   └── ...
│
├── services/
│   ├── task_reports_service.py         ⏳ TODO (CRUD, бизнес-логика)
│   └── task_reports_reminder.py        ⏳ TODO (система напоминаний)
│
├── modules/
│   └── task_reports/
│       ├── __init__.py                 ⏳ TODO
│       ├── router.py                   ⏳ TODO (главный роутер)
│       ├── states.py                   ⏳ TODO (FSM states)
│       ├── handlers.py                 ⏳ TODO (callback handlers)
│       ├── helpers.py                  ⏳ TODO (вспомогательные функции)
│       └── user_mapping.py             ⏳ TODO (Plane name → Telegram)
│
├── webhooks/
│   └── plane_handlers.py               ⏳ TODO (webhook от n8n)
│
└── main.py                             ⏳ TODO (регистрация роутеров)

alembic/versions/
└── 004_add_task_reports.py             ✅ ГОТОВО (миграция БД)

docs/
├── TASK_REPORTS_PLAN.md                📝 ЭТОТ ФАЙЛ
└── TASK_REPORTS_API.md                 ⏳ TODO (API документация)
```

---

## 🔄 Поток данных (детально)

### 1. Plane → n8n webhook

**Когда**: Задача переведена в Done в Plane

**n8n получает:**
```json
{
  "event": "issue",
  "action": "updated",
  "activity": {
    "actor": {
      "display_name": "Dmitriy Gusev",
      "first_name": "Dmitriy",
      "email": "dmitriy@example.com",
      "id": "user_uuid"
    },
    "field": "state",
    "old_value": "in_progress_state_id",
    "new_value": "done_state_id"
  },
  "data": {
    "issue": "issue_uuid",
    "project": "project_uuid"
  }
}
```

**n8n обрабатывает:**
```javascript
// В n8n workflow добавляем проверку
const webhookData = $json.body;

// Проверяем что статус изменён на Done
if (webhookData.activity?.field === 'state') {
  // Получаем детали задачи
  const issue = await getIssueDetails(webhookData.data.issue);

  // Проверяем что новый статус = Done (по названию)
  if (issue.state.name === 'Done' || issue.state.group === 'completed') {

    // Извлекаем support_request_id из description
    const supportRequestId = extractSupportRequestId(issue.description_html);

    // Отправляем webhook в бота
    await fetch('https://your-bot.com/webhooks/task-completed', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        plane_issue_id: issue.id,
        plane_sequence_id: issue.sequence_id,
        plane_project_id: issue.project,
        task_title: issue.name,
        task_description: issue.description_html,
        closed_by: webhookData.activity.actor,
        closed_at: new Date().toISOString(),
        support_request_id: supportRequestId
      })
    });
  }
}
```

### 2. Бот получает webhook

**Endpoint**: `POST /webhooks/task-completed`

**Handler**: `app/webhooks/plane_handlers.py`

```python
async def handle_task_completed(request: Request):
    """Обработка закрытия задачи в Plane"""

    # Парсим данные
    data = await request.json()

    # Создаём TaskReport
    report = await task_reports_service.create_from_webhook(
        plane_issue_id=data['plane_issue_id'],
        plane_sequence_id=data['plane_sequence_id'],
        task_title=data['task_title'],
        task_description=data.get('task_description'),
        closed_by_plane_name=data['closed_by']['display_name'],
        closed_at=data['closed_at'],
        support_request_id=data.get('support_request_id'),
        webhook_payload=json.dumps(data)
    )

    # Маппинг Plane name → Telegram
    telegram_data = await map_plane_user_to_telegram(
        data['closed_by']['display_name']
    )

    # Обновляем Telegram данные
    await task_reports_service.update_telegram_info(
        report.id,
        telegram_username=telegram_data['username'],
        telegram_id=telegram_data['user_id']
    )

    # Пытаемся автозаполнить из Work Journal (если есть)
    await task_reports_service.try_autofill_from_journal(report.id)

    # Отправляем форму админу
    await send_report_form_to_admin(report)

    return {'success': True, 'report_id': report.id}
```

### 3. Админ получает форму

**Сообщение админу** (в ЛС):

```
✅ Задача закрыта: #56

📝 [Тест] Проблема с сайтом

⚠️ ТРЕБУЕТСЯ ОТЧЁТ!

Опишите что было сделано для клиента.

[📝 Написать отчёт]  [⏭️ Пропустить (TODO)]
```

**Кнопки:**
- `report_write_{report_id}` - начать писать отчёт (FSM)
- `report_skip_{report_id}` - пропустить (ЗАГЛУШЕНО, автоотчёт в будущем)

### 4. FSM: Заполнение отчёта

**State 1**: `TaskReportStates.waiting_for_report`

Админ нажал "Написать отчёт":
```python
@router.callback_query(F.data.startswith("report_write_"))
async def start_writing_report(callback: CallbackQuery, state: FSMContext):
    report_id = int(callback.data.split("_")[2])

    # Получаем отчёт
    report = await task_reports_service.get(report_id)

    # Пытаемся подставить данные из Work Journal
    suggested_text = await get_suggested_report_text(report)

    await state.set_state(TaskReportStates.waiting_for_report)
    await state.update_data(
        report_id=report_id,
        suggested_text=suggested_text
    )

    message = "📝 Опишите что было сделано:\n\n"
    if suggested_text:
        message += f"💡 Предзаполнено из Work Journal:\n\n{suggested_text}\n\n"
        message += "Можете редактировать или отправить как есть."

    await callback.message.answer(
        message,
        reply_markup=ForceReply(
            selective=True,
            input_field_placeholder="Текст отчёта для клиента..."
        )
    )
```

Админ отправляет текст:
```python
@router.message(TaskReportStates.waiting_for_report, F.text)
async def receive_report_text(message: Message, state: FSMContext):
    data = await state.get_data()
    report_id = data['report_id']

    # Сохраняем отчёт как draft
    await task_reports_service.save_draft(
        report_id=report_id,
        report_text=message.text,
        submitted_by=message.from_user.id
    )

    # Переходим к проверке
    await state.set_state(TaskReportStates.reviewing_report)

    # Показываем превью
    await show_report_preview(message, report_id, message.text)
```

**State 2**: `TaskReportStates.reviewing_report`

Показываем превью:
```python
async def show_report_preview(message, report_id, report_text):
    report = await task_reports_service.get(report_id)

    preview = (
        f"📋 **Превью отчёта для клиента:**\n\n"
        f"✅ **Задача #{report.plane_sequence_id} выполнена!**\n\n"
        f"📝 **Что было сделано:**\n\n{report_text}\n\n"
        f"👤 Исполнитель: {report.closed_by_telegram_username}\n"
        f"📅 Дата: {report.closed_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"─────────────────────\n"
        f"Всё верно?"
    )

    await message.answer(
        preview,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ Отправить клиенту",
                callback_data=f"report_approve_{report_id}"
            )],
            [InlineKeyboardButton(
                text="✏️ Редактировать",
                callback_data=f"report_edit_{report_id}"
            )],
            [InlineKeyboardButton(
                text="❌ Отменить",
                callback_data=f"report_cancel_{report_id}"
            )]
        ]),
        parse_mode="Markdown"
    )
```

### 5. Отправка клиенту

Админ нажал "Отправить клиенту":
```python
@router.callback_query(F.data.startswith("report_approve_"))
async def approve_and_send(callback: CallbackQuery, state: FSMContext):
    report_id = int(callback.data.split("_")[2])

    # Одобряем отчёт
    report = await task_reports_service.approve(report_id)

    # Формируем сообщение для клиента
    client_message = format_client_message(report)

    # Отправляем в чат (reply если можем)
    await send_to_client_chat(report, client_message)

    # Обновляем статус
    await task_reports_service.mark_as_sent(report_id)

    # Уведомляем админа
    await callback.message.edit_text(
        f"✅ Отчёт отправлен клиенту в чат!\n\n"
        f"📋 Задача: #{report.plane_sequence_id}\n"
        f"💬 Чат: {report.client_chat_id}",
        reply_markup=None
    )

    await state.clear()
```

### 6. Система напоминаний

**Scheduler job**: каждые 30 минут

```python
async def check_pending_reports():
    """Проверяет pending отчёты и шлёт напоминания"""

    # Получаем все pending отчёты
    pending = await task_reports_service.get_pending_reports()

    for report in pending:
        hours_passed = report.hours_since_closed

        # Логика эскалации
        if hours_passed >= 6 and report.reminder_level < 3:
            await send_critical_reminder(report)
        elif hours_passed >= 3 and report.reminder_level < 2:
            await send_urgent_reminder(report)
        elif hours_passed >= 1 and report.reminder_level < 1:
            await send_gentle_reminder(report)

async def send_gentle_reminder(report):
    """Уровень 1: Мягкое напоминание"""
    await bot.send_message(
        chat_id=report.closed_by_telegram_id,
        text=(
            f"⏰ Напоминание\n\n"
            f"Не забудьте заполнить отчёт по задаче:\n"
            f"📋 #{report.plane_sequence_id} - {report.task_title}\n\n"
            f"Клиент ждёт информации."
        ),
        reply_markup=quick_report_button(report.id)
    )
    await task_reports_service.update_reminder(report.id, level=1)

async def send_urgent_reminder(report):
    """Уровень 2: Срочное напоминание"""
    await bot.send_message(
        chat_id=report.closed_by_telegram_id,
        text=(
            f"⚠️ СРОЧНО: Отчёт не заполнен!\n\n"
            f"Задача закрыта уже {int(report.hours_since_closed)} часов назад:\n"
            f"📋 #{report.plane_sequence_id}\n\n"
            f"Пожалуйста, заполните отчёт СЕЙЧАС."
        ),
        reply_markup=quick_report_button(report.id)
    )
    await task_reports_service.update_reminder(report.id, level=2)

async def send_critical_reminder(report):
    """Уровень 3: Критическое напоминание"""

    # Админу
    await bot.send_message(
        chat_id=report.closed_by_telegram_id,
        text=(
            f"🔥 КРИТИЧНО: Отчёт не заполнен {int(report.hours_since_closed)} часов!\n\n"
            f"📋 Задача: #{report.plane_sequence_id}\n"
            f"{report.task_title}\n\n"
            f"⚠️ Клиент давно ждёт ответа!\n"
            f"Заполните отчёт НЕМЕДЛЕННО или делегируйте другому админу."
        ),
        reply_markup=quick_report_button(report.id)
    )

    # Уведомляем остальных админов
    await notify_other_admins(report)

    await task_reports_service.update_reminder(report.id, level=3)
```

---

## 🔗 Интеграция с Work Journal

### Автозаполнение отчёта

Когда создаётся TaskReport, пытаемся найти связанную запись в Work Journal:

```python
async def try_autofill_from_journal(report_id: int):
    """Пытается автозаполнить отчёт из Work Journal"""

    report = await task_reports_service.get(report_id)

    if not report.support_request_id:
        return False

    # Ищем записи Work Journal за последние 7 дней
    # где упоминается номер задачи или связано с проектом
    entries = await work_journal_service.search_related_entries(
        support_request_id=report.support_request_id,
        plane_sequence_id=report.plane_sequence_id,
        days_back=7
    )

    if not entries:
        return False

    # Формируем предзаполненный текст
    suggested_text = format_journal_entries_as_report(entries)

    # Сохраняем как draft с пометкой
    await task_reports_service.save_draft(
        report_id=report_id,
        report_text=suggested_text,
        auto_filled_from_journal=True,
        work_journal_entry_id=entries[0].id
    )

    return True
```

---

## ✅ РЕАЛИЗОВАНО: Система напоминаний

### Автоматические напоминания каждые 30 минут

Реализовано в `app/services/scheduler.py` - метод `_reminders_loop()`:

**Логика напоминаний:**
- ⏰ **Уровень 1 (1 час)**: Мягкое напоминание админу, который закрыл задачу
- ⚠️ **Уровень 2 (3 часа)**: Срочное напоминание тому же админу
- 🚨 **Уровень 3 (6+ часов)**: КРИТИЧНО - уведомляются ВСЕ админы

**Интервалы:**
- Проверка каждые 30 минут
- Минимум 25 минут между повторными напоминаниями одному админу
- Подсчёт reminder_count в БД

**Реализация:**
```python
async def _reminders_loop(self):
    """Цикл проверки и отправки напоминаний об отчётах каждые 30 минут"""
    while self.running:
        # Получаем pending отчёты
        pending_reports = await task_reports_service.get_pending_reports(session)

        for report in pending_reports:
            hours_elapsed = report.hours_since_closed

            # Определяем уровень
            if hours_elapsed >= 6:
                reminder_level = 3  # Критично - всем админам
            elif hours_elapsed >= 3:
                reminder_level = 2  # Срочно
            elif hours_elapsed >= 1:
                reminder_level = 1  # Напоминание
            else:
                continue  # Пропускаем (ещё не прошёл час)

            # Отправляем напоминание
            await send_reminder_to_admins(report, reminder_level)

            # Обновляем статистику
            await task_reports_service.update_reminder_sent(
                task_report_id=report.id,
                reminder_level=reminder_level
            )
```

**Интеграция с scheduler:**
- Запускается одновременно с cache_sync_loop и daily_tasks_loop
- Использует `daily_tasks_service.bot_instance` для отправки сообщений
- Graceful shutdown при остановке бота

---

## 🎨 Маппинг Plane → Telegram

### Таблица соответствий

```python
# app/modules/task_reports/user_mapping.py

PLANE_TO_TELEGRAM = {
    # Дмитрий Гусев
    'Dmitriy Gusev': {'username': '@strikerstr', 'user_id': 123456789},
    'Dmitry Gusev': {'username': '@strikerstr', 'user_id': 123456789},
    'Гусев Дмитрий': {'username': '@strikerstr', 'user_id': 123456789},

    # Тимофей Батырев
    'Тимофей Батырев': {'username': '@spiritphoto', 'user_id': 987654321},
    'Timofey Batyrev': {'username': '@spiritphoto', 'user_id': 987654321},

    # Константин Макейкин
    'Konstantin Makeykin': {'username': '@zardes', 'user_id': 28795547},
    'Константин Макейкин': {'username': '@zardes', 'user_id': 28795547},
}

async def map_plane_user_to_telegram(plane_name: str) -> dict:
    """Маппинг Plane пользователя на Telegram"""

    # Прямое соответствие
    if plane_name in PLANE_TO_TELEGRAM:
        return PLANE_TO_TELEGRAM[plane_name]

    # Поиск по частичному совпадению
    name_lower = plane_name.lower()
    for key, value in PLANE_TO_TELEGRAM.items():
        if name_lower in key.lower() or key.lower() in name_lower:
            return value

    # Не нашли - возвращаем дефолт
    return {
        'username': f'_{plane_name}_',
        'user_id': None
    }
```

---

## ⚙️ Конфигурация

### Переменные окружения

```bash
# Webhook URL для n8n (чтобы бот мог принимать события)
TASK_REPORTS_WEBHOOK_URL=https://your-bot.com/webhooks/task-completed
TASK_REPORTS_WEBHOOK_SECRET=your_secret_key

# Интервал напоминаний (минуты)
TASK_REPORTS_REMINDER_INTERVAL=30

# Уровни напоминаний (часы)
TASK_REPORTS_GENTLE_AFTER_HOURS=1
TASK_REPORTS_URGENT_AFTER_HOURS=3
TASK_REPORTS_CRITICAL_AFTER_HOURS=6
```

---

## 🧪 Тестирование

### План тестов

1. **Unit тесты**:
   - `test_task_reports_service.py` - CRUD операции
   - `test_user_mapping.py` - маппинг Plane → Telegram
   - `test_autofill.py` - автозаполнение из Journal

2. **Integration тесты**:
   - `test_webhook_flow.py` - полный цикл от webhook до БД
   - `test_fsm_flow.py` - FSM states корректно работают
   - `test_reminders.py` - система напоминаний

3. **E2E тесты**:
   - `test_full_cycle.py` - закрыть задачу → заполнить отчёт → клиент получил

### Тестовые сценарии

```python
# test_full_cycle.py

async def test_task_closed_to_client_notified():
    """Полный цикл: Plane Done → Отчёт → Клиент"""

    # 1. Симулируем webhook от n8n
    webhook_data = {
        'plane_issue_id': 'test-uuid',
        'plane_sequence_id': 999,
        'task_title': 'Test Task',
        'closed_by': {'display_name': 'Konstantin Makeykin'},
        'support_request_id': 1
    }

    # 2. Вызываем webhook handler
    response = await client.post('/webhooks/task-completed', json=webhook_data)
    assert response.status_code == 200

    # 3. Проверяем что TaskReport создан
    report = await task_reports_service.get_by_plane_issue('test-uuid')
    assert report is not None
    assert report.status == 'pending'

    # 4. Симулируем заполнение отчёта админом
    await task_reports_service.save_draft(
        report.id,
        report_text='Проблема исправлена',
        submitted_by=28795547
    )

    # 5. Одобряем и отправляем
    await task_reports_service.approve(report.id)

    # 6. Проверяем что статус обновился
    report = await task_reports_service.get(report.id)
    assert report.status == 'sent_to_client'
    assert report.client_notified_at is not None
```

---

## 📝 Чеклист разработки

### Этап 1: Основа (БД и сервисы)
- [x] Создать TaskReport модель
- [x] Создать миграцию БД
- [ ] Реализовать TaskReportsService (CRUD)
- [ ] Реализовать user mapping (Plane → Telegram)

### Этап 2: Webhook и создание отчётов
- [ ] Создать webhook endpoint /webhooks/task-completed
- [ ] Реализовать обработку webhook от n8n
- [ ] Реализовать автозаполнение из Work Journal
- [ ] Отправка формы админу

### Этап 3: FSM для заполнения отчётов
- [ ] Создать FSM states (TaskReportStates)
- [ ] Реализовать handler: начать писать отчёт
- [ ] Реализовать handler: получить текст отчёта
- [ ] Реализовать handler: показать превью
- [ ] Реализовать handler: одобрить и отправить
- [ ] Реализовать handler: редактировать
- [ ] Реализовать handler: отменить

### Этап 4: Отправка клиенту
- [ ] Форматирование сообщения для клиента
- [ ] Отправка в чат (reply на исходное сообщение)
- [ ] Обновление статуса отчёта

### Этап 5: Система напоминаний
- [ ] Создать ReminderService
- [ ] Реализовать логику эскалации (gentle → urgent → critical)
- [ ] Добавить job в scheduler (каждые 30 мин)
- [ ] Уведомление других админов (при critical)

### Этап 6: Интеграция
- [ ] Обновить n8n workflow (добавить проверку Done + отправку webhook)
- [ ] Зарегистрировать роутер в main.py
- [ ] Протестировать полный цикл
- [ ] Обновить документацию

### Этап 7: Доп. фичи (опционально)
- [ ] Шаблоны отчётов
- [ ] История отчётов админа (/my_reports)
- [ ] Автоотчёт (если админ пропустил) - ЗАГЛУШЕНО
- [ ] Статистика по отчётам
- [ ] Экспорт отчётов

---

## 🚀 Порядок реализации

### День 1: Фундамент
1. TaskReportsService (CRUD)
2. User mapping
3. Webhook handler (базовый)

### День 2: FSM и формы
1. FSM states
2. Handlers для заполнения
3. Отправка клиенту

### День 3: Напоминания и интеграция
1. ReminderService
2. Scheduler job
3. n8n workflow update
4. Тестирование

---

## 📚 Полезные ссылки

- [Aiogram FSM Documentation](https://docs.aiogram.dev/en/latest/dispatcher/finite_state_machine/index.html)
- [SQLAlchemy Relationships](https://docs.sqlalchemy.org/en/14/orm/basic_relationships.html)
- [n8n Webhook Node](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/)
- [Plane API Webhooks](https://developers.plane.so/webhooks/intro-webhooks)

---

**Последнее обновление**: 2025-10-07
**Статус**: 🟡 В разработке (2/10 задач готовы)
**Разработчик**: Claude + @zardes
