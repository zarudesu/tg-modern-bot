# Обновление существующего n8n Plane Workflow

## 📋 Краткая инструкция

Нужно добавить в существующий Plane workflow новый HTTP Request node для отправки уведомления боту при закрытии задачи.

---

## 🔧 Шаги настройки

### 1. Открыть существующий Plane Workflow

Перейдите в n8n: `https://n8n.hhivp.com`

Найдите workflow, который обрабатывает события Plane (например, тот который отправляет в work-journal).

### 2. Добавить IF Node для проверки статуса

Если ещё нет, добавьте проверку:

```
IF Node: "Check if task is Done"
- Condition: state.name == "Done"
  OR
- Condition: new_value == "Done"
```

### 3. Добавить HTTP Request к боту

После IF node добавьте HTTP Request:

**Settings:**
- **Method**: POST
- **URL**: `http://telegram-bot-app:8080/webhooks/task-completed`
  (если в той же Docker network)
  или
  `http://your-server-ip:8080/webhooks/task-completed`
- **Authentication**: None
- **Body Content Type**: JSON
- **Body Parameters**:

```json
{
  "plane_issue_id": "{{ $json.issue.id }}",
  "plane_sequence_id": {{ $json.issue.sequence_id }},
  "plane_project_id": "{{ $json.issue.project_id }}",
  "task_title": "{{ $json.issue.name }}",
  "task_description": "{{ $json.issue.description }}",
  "closed_by": {
    "display_name": "{{ $json.activity.actor.display_name }}",
    "first_name": "{{ $json.activity.actor.first_name }}",
    "email": "{{ $json.activity.actor.email }}"
  },
  "closed_at": "{{ $json.timestamp }}",
  "support_request_id": null
}
```

**Note**: Если есть логика извлечения `support_request_id` из description, используйте Function node (см. полную инструкцию).

### 4. Тестирование

1. Сохраните workflow
2. Активируйте workflow
3. Переведите тестовую задачу в Plane в статус "Done"
4. Проверьте логи бота:

```bash
docker-compose -f docker-compose.bot.yml logs --since 5m | grep task-completed
```

Ожидаемые логи:
```
📨 Received task-completed webhook: plane_issue=..., seq_id=...
✅ Created TaskReport #N for Plane issue ...
✅ Notified admin ... about TaskReport #N
```

---

## 🎯 Альтернатива: Отдельный Webhook

Если не хотите менять существующий workflow, создайте новый:

1. **New Workflow**: "Plane Task Completed"
2. **Webhook Trigger**: Plane issue updated
3. **IF**: state == "Done"
4. **HTTP Request**: к боту (как описано выше)

---

## 📝 Извлечение support_request_id (опционально)

Если хотите автоматически связывать с support requests, добавьте Function node:

```javascript
// Извлекаем support_request_id из описания
const description = $input.item.json.issue.description || '';
let supportRequestId = null;

const match = description.match(/support_request_id[=:\s]+(\d+)/i);
if (match) {
  supportRequestId = parseInt(match[1]);
}

return {
  json: {
    ...$input.item.json,
    extracted_support_request_id: supportRequestId
  }
};
```

Затем в HTTP Request используйте:
```json
{
  ...
  "support_request_id": {{ $json.extracted_support_request_id }}
}
```

---

## ✅ Проверка работы

### 1. Health Check

```bash
curl http://your-server:8080/health
```

Ответ: `{"status": "ok", "service": "telegram-bot-webhooks", ...}`

### 2. Manual Test

```bash
curl -X POST http://your-server:8080/webhooks/task-completed \
  -H "Content-Type: application/json" \
  -d '{
    "plane_issue_id": "test-uuid",
    "plane_sequence_id": 999,
    "task_title": "Тест",
    "closed_by": {"display_name": "Zardes", "email": "zarudesu@gmail.com"},
    "closed_at": "2025-10-07T12:00:00Z"
  }'
```

Ответ: `{"status": "processed", "task_report_id": N, ...}`

### 3. Проверка в Telegram

Админ должен получить сообщение:

```
📋 **Требуется отчёт о выполненной задаче!**

**Задача:** #999
**Название:** Тест
**Закрыл:** Zardes

[Кнопка: 📝 Заполнить отчёт]
```

---

## 🔍 Troubleshooting

### Webhook не доходит

```bash
# Проверить что бот запущен
docker ps | grep telegram-bot-app

# Проверить порт 8080
curl http://localhost:8080/health

# Проверить логи
docker-compose -f docker-compose.bot.yml logs --tail=50
```

### TaskReport создаётся, но уведомление не приходит

```bash
# Проверить маппинг Plane → Telegram
docker logs telegram-bot-app | grep "No Telegram mapping"

# Должен быть в task_reports_service.py:
PLANE_TO_TELEGRAM_MAP = {
    "Zardes": {"telegram_id": 28795547},
    "zarudesu@gmail.com": {"telegram_id": 28795547}
}
```

---

## 📚 Полная документация

См. `/Users/zardes/Projects/tg-mordern-bot/docs/N8N_TASK_REPORTS_WORKFLOW.md`

---

## ⚡ Quick Summary

1. Откройте n8n workflow для Plane
2. Добавьте HTTP Request к `http://telegram-bot-app:8080/webhooks/task-completed`
3. Триггер: когда task status = "Done"
4. Payload: см. пример выше
5. Тестируйте: переведите задачу в Done → админ получит уведомление
