# Быстрая настройка n8n для Task Reports

## 🚀 Автоматическая настройка (рекомендуется)

### Шаг 1: Получите API ключ n8n

1. Откройте https://n8n.hhivp.com
2. Перейдите в **Settings → API**
3. Нажмите **Create API Key**
4. Скопируйте ключ

### Шаг 2: Запустите скрипт

```bash
export N8N_API_KEY='ваш-api-ключ'
bash setup_n8n_webhook.sh
```

Скрипт автоматически:
- ✅ Создаст новый workflow "Plane Task Completed → Bot"
- ✅ Настроит все nodes (Webhook, IF, Function, HTTP Request)
- ✅ Активирует workflow
- ✅ Выдаст webhook URL для настройки в Plane

### Шаг 3: Настройте Plane webhook

1. Откройте Plane.so → Settings → Webhooks
2. Create Webhook:
   - **URL**: `https://n8n.hhivp.com/webhook/plane-task-done`
   - **Events**: Issue Activity Updated
3. Save

### Шаг 4: Тестирование

Переведите любую задачу в Plane в статус "Done"

**Ожидаемый результат:**
- Админ получит уведомление в Telegram
- С кнопкой "📝 Заполнить отчёт"

---

## 📋 Ручная настройка (альтернатива)

Если не хотите использовать скрипт, см. `N8N_TASK_REPORTS_UPDATE.md`

---

## 🔍 Проверка работы

### Логи бота:

```bash
docker-compose -f docker-compose.bot.yml logs --since 5m | grep task-completed
```

Ожидаемые логи:
```
📨 Received task-completed webhook: plane_issue=..., seq_id=123
✅ Created TaskReport #1 for Plane issue 123
✅ Notified admin 28795547 about TaskReport #1
```

### Проверка в БД:

```sql
SELECT * FROM task_reports ORDER BY created_at DESC LIMIT 5;
```

---

## ⚙️ Что создаёт скрипт

Workflow с 4 nodes:

1. **Webhook Trigger** - принимает события от Plane
2. **IF Node** - проверяет что task status = "Done"
3. **Function Node** - трансформирует данные + извлекает support_request_id
4. **HTTP Request** - отправляет в бота

---

## 🐛 Troubleshooting

### API ключ не работает

Проверьте права доступа API ключа в n8n Settings

### Webhook не создаётся

```bash
# Проверить доступность n8n API
curl -H "X-N8N-API-KEY: $N8N_API_KEY" https://n8n.hhivp.com/api/v1/workflows
```

### Бот не получает webhook

```bash
# Проверить что webhook server запущен
curl http://localhost:8080/health
```

---

## 📚 Дополнительная информация

- Полная документация: `N8N_TASK_REPORTS_WORKFLOW.md`
- Обновление существующего workflow: `N8N_TASK_REPORTS_UPDATE.md`
