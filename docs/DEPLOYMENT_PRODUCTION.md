# Production Deployment Guide

Полное руководство по развертыванию и обновлению Telegram бота на production сервере rd.hhivp.com.

## Содержание

1. [Архитектура Deployment](#архитектура-deployment)
2. [Тестовый бот (параллельный)](#тестовый-бот-параллельный)
3. [Production бот (основной)](#production-бот-основной)
4. [n8n Workflow Setup](#n8n-workflow-setup)
5. [Task Reports System](#task-reports-system)
6. [Troubleshooting](#troubleshooting)

---

## Архитектура Deployment

### Два независимых окружения на одном сервере

```
rd.hhivp.com (45.10.53.234)
├── Production Bot (основной)
│   ├── Порт: 8080 (webhook server)
│   ├── PostgreSQL: 5432
│   ├── Redis: 6379
│   ├── Token: основной токен
│   └── Директория: /home/hhivp/tg-bot-prod/
│
└── Test Bot (тестовый, параллельный)
    ├── Порт: 8081 (webhook server)
    ├── PostgreSQL: 5434
    ├── Redis: 6380
    ├── Token: 862863686:AAGQPN8YnpCJtXvLLpvuv7elBAa5_x6sg5I
    └── Директория: /home/hhivp/tg-bot-test/
```

### Сетевая схема

```
Plane.so → n8n → Telegram Bot
         Webhook   (port 8080 prod / 8081 test)
```

**Важно**: n8n и бот в разных Docker networks, поэтому используется IP хоста (45.10.53.234).

---

## Тестовый бот (параллельный)

### 1. Подготовка локально

Убедитесь что код готов к deployment:

```bash
# 1. Проверьте что Dockerfile правильный (без sql/)
cat Dockerfile | grep -E "COPY|ADD"

# 2. Проверьте что чувствительные данные не попадут в git
git status
cat .gitignore | grep -E "\.env|SECRETS"

# 3. Запустите локальные тесты
make test

# 4. Commit и push
git add .
git commit -m "🚀 Prepare for test bot deployment"
git push origin main
```

### 2. Deployment на сервер

```bash
# SSH на сервер
ssh root@rd.hhivp.com

# Создайте директорию для тестового бота
mkdir -p /home/hhivp/tg-bot-test
cd /home/hhivp/tg-bot-test

# Clone репозиторий (HTTPS, не SSH)
git clone https://github.com/zarudesu/tg-modern-bot.git .

# Создайте .env файл
cat > .env <<'EOF'
TELEGRAM_TOKEN=862863686:AAGQPN8YnpCJtXvLLpvuv7elBAa5_x6sg5I
ADMIN_USER_IDS=28795547
DATABASE_URL=postgresql+asyncpg://bot_user_test:bot_test_pass_2024@localhost:5434/telegram_bot_test
REDIS_URL=redis://:redis_test_pass_2024@localhost:6380
N8N_WEBHOOK_URL=https://n8n.hhivp.com/webhook/work-journal
PLANE_API_URL=https://plane.hhivp.com
PLANE_API_TOKEN=plane_api_15504fe9f81f4a819a79ff8409135447
WORK_JOURNAL_GROUP_CHAT_ID=-1001682373643
EOF

# Создайте docker-compose.test.yml
cat > docker-compose.test.yml <<'EOF'
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: telegram-bot-postgres-test
    environment:
      POSTGRES_DB: telegram_bot_test
      POSTGRES_USER: bot_user_test
      POSTGRES_PASSWORD: bot_test_pass_2024
    volumes:
      - postgres_data_test:/var/lib/postgresql/data
    ports:
      - '5434:5432'
    networks:
      - telegram-bot-network-test
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    container_name: telegram-bot-redis-test
    command: redis-server --requirepass redis_test_pass_2024
    volumes:
      - redis_data_test:/data
    ports:
      - '6380:6379'
    networks:
      - telegram-bot-network-test
    restart: unless-stopped

  bot:
    build: .
    container_name: telegram-bot-app-test
    env_file:
      - .env
    depends_on:
      - postgres
      - redis
    ports:
      - '8081:8080'  # Webhook server на порту 8081
    networks:
      - telegram-bot-network-test
    restart: unless-stopped
    volumes:
      - ./logs:/app/logs
      - ./backups:/app/backups

volumes:
  postgres_data_test:
  redis_data_test:

networks:
  telegram-bot-network-test:
    driver: bridge
EOF

# Запустите тестовый бот
docker-compose -f docker-compose.test.yml up -d --build

# Проверьте логи
docker-compose -f docker-compose.test.yml logs -f bot
```

### 3. Проверка работы

```bash
# Проверьте что все контейнеры запущены
docker ps | grep test

# Проверьте логи запуска
docker-compose -f docker-compose.test.yml logs bot | grep "Bot started"

# Проверьте webhook server
curl http://localhost:8081/health

# Проверьте database connection
docker-compose -f docker-compose.test.yml exec postgres psql -U bot_user_test -d telegram_bot_test -c "\dt"
```

### 4. Обновление тестового бота

```bash
cd /home/hhivp/tg-bot-test

# Pull последние изменения
git pull origin main

# Rebuild и restart
docker-compose -f docker-compose.test.yml down
docker-compose -f docker-compose.test.yml up -d --build

# Проверьте логи
docker-compose -f docker-compose.test.yml logs -f bot
```

---

## Production бот (основной)

### ⚠️ ВАЖНО: Процедура обновления production

**НЕ ДЕЛАЙТЕ это без проверки на тестовом боте!**

```bash
# 1. Проверьте что изменения протестированы на test боте
ssh root@rd.hhivp.com
cd /home/hhivp/tg-bot-test
docker-compose -f docker-compose.test.yml logs bot | tail -100

# 2. Создайте backup production БД
cd /home/hhivp/tg-bot-prod
docker-compose exec postgres pg_dump -U bot_user telegram_bot > backup_$(date +%Y%m%d_%H%M%S).sql

# 3. Pull изменения
git pull origin main

# 4. Запустите обновление
docker-compose down
docker-compose up -d --build

# 5. Проверьте запуск
docker-compose logs -f bot

# 6. Если что-то пошло не так - откат
docker-compose down
git reset --hard HEAD~1
docker-compose up -d --build
```

### Production конфигурация

**Директория**: `/home/hhivp/tg-bot-prod/`

**`.env`** (основной):
```bash
TELEGRAM_TOKEN=<основной токен>
ADMIN_USER_IDS=28795547,132228544
DATABASE_URL=postgresql+asyncpg://bot_user:<pass>@localhost:5432/telegram_bot
REDIS_URL=redis://:<pass>@localhost:6379
N8N_WEBHOOK_URL=https://n8n.hhivp.com/webhook/work-journal
PLANE_API_URL=https://plane.hhivp.com
PLANE_API_TOKEN=plane_api_15504fe9f81f4a819a79ff8409135447
WORK_JOURNAL_GROUP_CHAT_ID=-1001682373643
```

**`docker-compose.yml`**:
```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: telegram-bot-postgres
    environment:
      POSTGRES_DB: telegram_bot
      POSTGRES_USER: bot_user
      POSTGRES_PASSWORD: <production_password>
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - '5432:5432'
    networks:
      - telegram-bot-network
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    container_name: telegram-bot-redis
    command: redis-server --requirepass <production_password>
    volumes:
      - redis_data:/data
    ports:
      - '6379:6379'
    networks:
      - telegram-bot-network
    restart: unless-stopped

  bot:
    build: .
    container_name: telegram-bot-app
    env_file:
      - .env
    depends_on:
      - postgres
      - redis
    ports:
      - '8080:8080'
    networks:
      - telegram-bot-network
    restart: unless-stopped
    volumes:
      - ./logs:/app/logs
      - ./backups:/app/backups

volumes:
  postgres_data:
  redis_data:

networks:
  telegram-bot-network:
    driver: bridge
```

---

## n8n Workflow Setup

### Конфигурация для Task Reports

n8n находится по адресу: **https://n8n.hhivp.com**

### 1. Создание/обновление workflow через API

**Локально** (с вашего компьютера):

```bash
# n8n API Key (из SECRETS.md)
API_KEY='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'

# Для тестового бота (port 8081)
curl -X POST https://n8n.hhivp.com/api/v1/workflows \
  -H "X-N8N-API-KEY: $API_KEY" \
  -H "Content-Type: application/json" \
  -d @/tmp/n8n_workflow_production.json

# Activate workflow (замените WORKFLOW_ID на полученный)
curl -X PATCH https://n8n.hhivp.com/api/v1/workflows/WORKFLOW_ID/activate \
  -H "X-N8N-API-KEY: $API_KEY"
```

**Для production бота** (port 8080):

Измените в workflow JSON:
```json
{
  "parameters": {
    "url": "http://45.10.53.234:8080/webhooks/task-completed",  // 8080 вместо 8081
    ...
  }
}
```

### 2. Настройка Plane webhook

В Plane.so (https://plane.hhivp.com):

1. Settings → Webhooks → Create Webhook
2. **URL**: `https://n8n.hhivp.com/webhook/plane-task-done-a7f3c9e2b1d4f8a6c3e9d2b7f4a1c8e5`
3. **Events**: Select "Issue updated"
4. **Secret**: оставьте пустым (мы используем длинный URL вместо подписей)
5. Save

### 3. Workflow структура

```
Plane → n8n Webhook → Filter (Function) → Transform → HTTP Request → Bot
```

**Filter Function** (отсеивает все кроме Done state changes):
```javascript
const body = $input.item.json.body;

if (body.event !== 'issue' || body.action !== 'updated') {
  return [];
}

if (body.activity.field !== 'state_id') {
  return [];
}

if (body.data.state.group !== 'completed') {
  return [];
}

return [$input.item];
```

**Transform Function** (формирует payload для бота):
```javascript
const data = $input.item.json.body.data;
const activity = $input.item.json.body.activity;
const description = data.description_stripped || '';
let supportRequestId = null;

const match = description.match(/support_request_id[=:\s]+(\d+)/i);
if (match) {
  supportRequestId = parseInt(match[1]);
}

const payload = {
  plane_issue_id: data.id,
  plane_sequence_id: data.sequence_id,
  plane_project_id: data.project,
  task_title: data.name,
  task_description: description,
  closed_by: {
    display_name: activity.actor.display_name,
    first_name: activity.actor.first_name,
    email: activity.actor.email
  },
  closed_at: data.completed_at,
  support_request_id: supportRequestId
};

return { json: payload };
```

---

## Task Reports System

### Проверка работы системы

```bash
# На сервере
ssh root@rd.hhivp.com
cd /home/hhivp/tg-bot-test  # или tg-bot-prod

# Мониторинг webhook событий
docker-compose -f docker-compose.test.yml logs -f bot | grep -E "(task-completed|TaskReport)"
```

### Тестирование flow

1. В Plane.so создайте задачу
2. Добавьте в описание: `support_request_id: 123`
3. Переведите задачу в статус **Done**
4. Проверьте:
   - n8n execution: https://n8n.hhivp.com/workflows
   - Логи бота: webhook получен
   - Telegram: админ получил уведомление

### Webhook endpoint

Бот принимает POST запросы на `/webhooks/task-completed`:

**Expected payload**:
```json
{
  "plane_issue_id": "uuid",
  "plane_sequence_id": 55,
  "plane_project_id": "uuid",
  "task_title": "Название задачи",
  "task_description": "Описание",
  "closed_by": {
    "display_name": "Имя",
    "first_name": "Константин",
    "email": "email@example.com"
  },
  "closed_at": "2025-10-07T03:23:29.421413Z",
  "support_request_id": 123
}
```

**Bot actions**:
1. Создает TaskReport в БД
2. Опционально обновляет WorkJournalEntry (если есть support_request_id)
3. Отправляет уведомление админу

---

## Troubleshooting

### Проблема: Бот не получает webhook от n8n

**Причина**: Docker networks изолированы

**Решение**: Используйте IP хоста, а не имя контейнера
```json
// ❌ НЕ РАБОТАЕТ
"url": "http://telegram-bot-app:8080/webhooks/task-completed"

// ✅ РАБОТАЕТ
"url": "http://45.10.53.234:8080/webhooks/task-completed"
```

### Проблема: n8n workflow падает с ошибкой crypto

**Причина**: n8n VM2 sandbox не поддерживает `require('crypto')`

**Решение**: Не используйте signature verification, используйте длинный случайный URL:
```
plane-task-done-a7f3c9e2b1d4f8a6c3e9d2b7f4a1c8e5
```

### Проблема: Dockerfile build error "sql/ not found"

**Решение**: Убедитесь что в Dockerfile нет строки:
```dockerfile
COPY sql/ ./sql/  # ❌ Удалить эту строку
```

### Проблема: Git clone на сервере не работает (SSH)

**Решение**: Используйте HTTPS вместо SSH:
```bash
# ❌ Может не работать
git clone git@github.com:zarudesu/tg-modern-bot.git

# ✅ Работает всегда
git clone https://github.com/zarudesu/tg-modern-bot.git
```

### Проблема: Port conflict при запуске test бота

**Причина**: Production бот уже использует порты

**Решение**: Test бот использует другие порты:
- Webhook: 8081 (вместо 8080)
- PostgreSQL: 5434 (вместо 5432)
- Redis: 6380 (вместо 6379)

### Проблема: Database migration failed

```bash
# Проверьте connection
docker-compose -f docker-compose.test.yml exec postgres psql -U bot_user_test -d telegram_bot_test

# Запустите миграции вручную
docker-compose -f docker-compose.test.yml exec bot alembic upgrade head

# Проверьте текущую версию
docker-compose -f docker-compose.test.yml exec bot alembic current
```

### Проблема: Бот не отвечает на команды

```bash
# 1. Проверьте что бот запущен
docker ps | grep bot

# 2. Проверьте логи на ошибки
docker-compose logs bot | grep ERROR

# 3. Проверьте токен
docker-compose exec bot env | grep TELEGRAM_TOKEN

# 4. Проверьте polling/webhook конфликты
# (бот должен использовать long polling, webhook только для /webhooks/*)
```

---

## Checklist перед deployment

### Pre-deployment

- [ ] Код протестирован локально (`make test`)
- [ ] Dockerfile правильный (нет `COPY sql/`)
- [ ] `.gitignore` содержит `.env`, `SECRETS.md`
- [ ] Изменения закоммичены и запушены в main
- [ ] n8n workflow подготовлен (правильный порт)

### Test Bot Deployment

- [ ] Создана директория `/home/hhivp/tg-bot-test/`
- [ ] Repository cloned via HTTPS
- [ ] `.env` файл создан с правильными credentials
- [ ] `docker-compose.test.yml` создан с правильными портами
- [ ] `docker-compose up -d --build` успешно
- [ ] Логи показывают "Bot started successfully"
- [ ] Webhook endpoint доступен: `curl http://localhost:8081/health`

### n8n Configuration

- [ ] Workflow создан через API
- [ ] Workflow активирован
- [ ] Plane webhook настроен с правильным URL
- [ ] Test event от Plane проходит успешно

### Testing

- [ ] Создана тестовая задача в Plane
- [ ] Задача переведена в Done status
- [ ] n8n execution показывает success
- [ ] Бот получил webhook (логи)
- [ ] TaskReport создан в БД
- [ ] Админ получил уведомление в Telegram

### Production Deployment (после тестирования!)

- [ ] Test бот работает без ошибок минимум 24 часа
- [ ] Создан backup production БД
- [ ] Production workflow создан с портом 8080
- [ ] Plane webhook обновлен на новый workflow
- [ ] Production бот обновлен (`git pull`, `docker-compose up -d --build`)
- [ ] Проверена работа на production

---

## Полезные команды

```bash
# Просмотр всех контейнеров (prod + test)
docker ps -a | grep telegram-bot

# Логи с фильтрацией
docker-compose logs bot | grep -E "(ERROR|WARNING|TaskReport)"

# Restart без rebuild
docker-compose restart bot

# Полная пересборка
docker-compose down && docker-compose up -d --build

# Database backup
docker-compose exec postgres pg_dump -U bot_user telegram_bot > backup.sql

# Database restore
cat backup.sql | docker-compose exec -T postgres psql -U bot_user telegram_bot

# Проверка n8n workflows
curl -H "X-N8N-API-KEY: $API_KEY" https://n8n.hhivp.com/api/v1/workflows

# Проверка n8n executions
curl -H "X-N8N-API-KEY: $API_KEY" https://n8n.hhivp.com/api/v1/executions
```

---

## Контакты и ссылки

- **GitHub**: https://github.com/zarudesu/tg-modern-bot
- **n8n**: https://n8n.hhivp.com
- **Plane**: https://plane.hhivp.com
- **Server**: rd.hhivp.com (45.10.53.234)
- **Admin Telegram**: @zarudesu

---

Последнее обновление: 2025-10-07
