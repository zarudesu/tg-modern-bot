# n8n Workflow для Task Reports

Этот документ описывает настройку n8n workflow для автоматической отправки отчётов о выполненных задачах клиентам.

## 📋 Обзор системы

**Цель:** Когда задача в Plane переводится в статус "Done", автоматически:
1. Создаётся TaskReport в БД бота
2. Админу приходит уведомление в Telegram
3. Админ заполняет отчёт через FSM workflow
4. Отчёт отправляется клиенту

## 🔗 Webhook Endpoint

**URL:** `http://your-bot-url:8080/webhooks/task-completed`

**Метод:** `POST`

**Content-Type:** `application/json`

**Ожидаемая структура данных:**

```json
{
  "plane_issue_id": "uuid-задачи-в-plane",
  "plane_sequence_id": 123,
  "plane_project_id": "uuid-проекта",
  "task_title": "Название задачи",
  "task_description": "Полное описание задачи (может содержать support_request_id)",
  "closed_by": {
    "display_name": "Zardes",
    "first_name": "Zardes",
    "email": "zarudesu@gmail.com"
  },
  "closed_at": "2025-10-07T12:00:00Z",
  "support_request_id": 5
}
```

### Поля:

- `plane_issue_id` (**обязательно**): UUID задачи в Plane
- `plane_sequence_id`: Номер задачи (напр. 123 для HHIVP-123)
- `plane_project_id`: UUID проекта
- `task_title`: Название задачи
- `task_description`: Описание (используется для извлечения support_request_id)
- `closed_by`: Объект с данными админа, который закрыл задачу
  - `display_name` или `first_name`: Имя для маппинга на Telegram
  - `email`: Email для маппинга на Telegram
- `closed_at`: ISO timestamp когда задача была закрыта
- `support_request_id`: ID заявки поддержки (опционально, можно извлечь из description)

---

## 🛠️ Настройка n8n Workflow

### Шаг 1: Plane Webhook Trigger

1. Добавьте node "Plane Webhook" (или HTTP Webhook если нет встроенного)
2. Настройте фильтр событий:
   - Event type: `issue.activity.updated`
   - Filter: `new_value == "Done"` или аналогично

### Шаг 2: Извлечение данных из Plane webhook

Plane отправляет webhook в формате:

```json
{
  "event": "issue.activity.updated",
  "issue_id": "uuid",
  "activity": {
    "field": "state",
    "new_value": "Done",
    "old_value": "In Progress",
    "actor": {
      "id": "uuid",
      "display_name": "Zardes",
      "first_name": "Zardes",
      "email": "zarudesu@gmail.com"
    }
  },
  "issue": {
    "id": "uuid",
    "sequence_id": 123,
    "project_id": "uuid",
    "name": "Task title",
    "description": "Task description with support_request_id=5"
  },
  "timestamp": "2025-10-07T12:00:00Z"
}
```

### Шаг 3: Function Node для трансформации данных

Добавьте Function node с кодом:

```javascript
// Извлекаем данные из Plane webhook
const planeData = $input.item.json;

// Извлекаем support_request_id из описания (если есть)
let supportRequestId = null;
const description = planeData.issue.description || '';
const match = description.match(/support_request_id[=:\s]+(\d+)/i);
if (match) {
  supportRequestId = parseInt(match[1]);
}

// Формируем payload для бота
const botPayload = {
  plane_issue_id: planeData.issue.id,
  plane_sequence_id: planeData.issue.sequence_id,
  plane_project_id: planeData.issue.project_id,
  task_title: planeData.issue.name,
  task_description: description,
  closed_by: {
    display_name: planeData.activity.actor.display_name,
    first_name: planeData.activity.actor.first_name,
    email: planeData.activity.actor.email
  },
  closed_at: planeData.timestamp,
  support_request_id: supportRequestId
};

return {
  json: botPayload
};
```

### Шаг 4: HTTP Request Node к боту

1. Добавьте HTTP Request node
2. Настройки:
   - **Method**: POST
   - **URL**: `http://telegram-bot-app:8080/webhooks/task-completed`
     (если в той же Docker network) или `http://your-server-ip:8080/webhooks/task-completed`
   - **Authentication**: None (внутренняя сеть)
   - **Body Content Type**: JSON
   - **Specify Body**: Using Fields Below
   - **Body**: `{{ $json }}`

3. Headers (опционально):
   ```
   Content-Type: application/json
   ```

### Шаг 5: Error Handling (рекомендуется)

Добавьте Error Workflow с уведомлением в Telegram при ошибке:

```javascript
// В случае ошибки - отправить админу
const errorMessage = `
❌ Ошибка отправки task report webhook!

Задача: ${$json.task_title}
Plane ID: ${$json.plane_sequence_id}
Ошибка: ${$json.error}
`;

// Отправить через Telegram Bot API
```

---

## 🧪 Тестирование Webhook

### Ручное тестирование с curl

```bash
curl -X POST http://localhost:8080/webhooks/task-completed \
  -H "Content-Type: application/json" \
  -d '{
    "plane_issue_id": "test-uuid-12345",
    "plane_sequence_id": 999,
    "plane_project_id": "project-uuid",
    "task_title": "Тестовая задача для проверки webhook",
    "task_description": "Описание задачи, support_request_id=1",
    "closed_by": {
      "display_name": "Zardes",
      "email": "zarudesu@gmail.com"
    },
    "closed_at": "2025-10-07T12:00:00Z",
    "support_request_id": 1
  }'
```

**Ожидаемый результат:**
```json
{
  "status": "processed",
  "task_report_id": 1,
  "plane_sequence_id": 999
}
```

### Проверка в Telegram

После отправки webhook админ должен получить сообщение:

```
📋 **Требуется отчёт о выполненной задаче!**

**Задача:** #999
**Название:** Тестовая задача для проверки webhook
**Закрыл:** Zardes

[Кнопка: 📝 Заполнить отчёт]
```

---

## 🔍 Проверка логов

### Логи бота

```bash
# Проверить что webhook получен
docker-compose -f docker-compose.bot.yml logs --since 5m | grep "task-completed"

# Проверить создание TaskReport
docker-compose -f docker-compose.bot.yml logs --since 5m | grep "Created TaskReport"

# Проверить отправку уведомления админу
docker-compose -f docker-compose.bot.yml logs --since 5m | grep "Notified admin"
```

Ожидаемые логи:
```
📨 Received task-completed webhook: plane_issue=test-uuid-12345, seq_id=999
✅ Created TaskReport #1 for Plane issue 999
✅ Notified admin 28795547 about TaskReport #1
```

---

## 🎨 Plane User → Telegram Mapping

Маппинг настраивается в `app/services/task_reports_service.py`:

```python
PLANE_TO_TELEGRAM_MAP = {
    "Zardes": {
        "telegram_username": "zardes",
        "telegram_id": 28795547
    },
    "zarudesu@gmail.com": {
        "telegram_username": "zardes",
        "telegram_id": 28795547
    },
    # Добавьте других админов здесь
}
```

**Важно:** Если админ не найден в маппинге, уведомление отправляется ВСЕМ админам из `ADMIN_USER_IDS`.

---

## 🔄 Автозаполнение из Work Journal

Если `support_request_id` указан, бот автоматически пытается найти записи в Work Journal:

- Ищет записи за последние 7 дней
- Где упоминается `plane_sequence_id` или привязано к `support_request_id`
- Формирует предзаполненный отчёт

Админ получит уведомление с пометкой:
```
✅ Отчёт автоматически заполнен из work journal
```

---

## 📊 Мониторинг и дебаг

### Проверка pending отчётов в БД

```sql
SELECT id, plane_sequence_id, task_title, closed_at, status, reminder_count
FROM task_reports
WHERE status = 'pending'
ORDER BY closed_at ASC;
```

### Проверка reminders

Система напоминаний запускается каждые 30 минут:

```bash
# Проверить логи reminders loop
docker-compose -f docker-compose.bot.yml logs --since 30m | grep "reminder"
```

Ожидаемые логи:
```
🔔 Starting task reports reminder check
📨 Found 2 pending task reports
✅ Sent reminder for TaskReport #1 (level 1, 1 admins)
```

---

## ⚠️ Troubleshooting

### Webhook не доходит до бота

1. Проверьте доступность endpoint:
   ```bash
   curl http://localhost:8080/health
   ```

2. Проверьте что бот запущен:
   ```bash
   docker ps | grep telegram-bot-app
   ```

3. Проверьте логи бота на ошибки:
   ```bash
   docker-compose -f docker-compose.bot.yml logs --tail=100 | grep ERROR
   ```

### TaskReport создаётся, но админ не получает уведомление

1. Проверьте маппинг Plane user → Telegram в логах:
   ```bash
   docker logs telegram-bot-app | grep "No Telegram mapping"
   ```

2. Проверьте что admin_id корректен в .env:
   ```bash
   grep ADMIN_USER_IDS .env
   ```

### Reminder не отправляются

1. Проверьте что scheduler запущен:
   ```bash
   docker logs telegram-bot-app | grep "scheduler"
   ```

2. Проверьте pending отчёты в БД (см. выше)

---

## 📝 Примечания

- Webhook server встроен в основное приложение бота
- Порт по умолчанию: 8080
- Endpoint: `/webhooks/task-completed`
- Автоматическое создание TaskReport с уведомлением админа
- FSM workflow для заполнения отчёта
- Система escalating reminders каждые 30 минут (1ч → 3ч → 6ч+)
- Auto-fill из Work Journal при наличии support_request_id

---

## ✅ Checklist настройки

- [ ] Webhook server запущен и доступен
- [ ] n8n workflow настроен и активен
- [ ] Plane webhook trigger подключен к событию "issue done"
- [ ] Function node трансформирует данные корректно
- [ ] HTTP Request node отправляет на правильный URL
- [ ] Маппинг Plane users → Telegram настроен
- [ ] Протестирован вручную через curl
- [ ] Админ получает уведомления
- [ ] FSM workflow работает (заполнение/редактирование/отправка)
- [ ] Reminders приходят согласно расписанию
- [ ] Auto-fill из Work Journal работает
