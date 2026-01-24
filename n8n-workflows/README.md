# n8n AI Workflows

Workflows для AI интеграции бота через n8n.

## Архитектура

```
┌──────────────────┐     ┌─────────────────────────────────────────┐
│   Telegram Bot   │     │                   n8n                   │
│                  │     │                                         │
│  Chat Monitor ───┼────►│  AI Task Detection                     │
│                  │     │  ├─ Webhook receive                    │
│  Voice Handler ──┼────►│  ├─ OpenRouter AI (free Llama/Mistral) │
│                  │     │  ├─ Plane API (create task)            │
│  ◄───────────────┼─────┤  └─ Callback to bot                    │
│  Webhooks        │     │                                         │
│  /ai/task-result │     │  AI Voice Report                       │
│  /ai/voice-result│     │  ├─ Webhook receive                    │
└──────────────────┘     │  ├─ Download voice file                │
                         │  ├─ Whisper transcription              │
                         │  ├─ OpenRouter AI (extract data)       │
                         │  ├─ Plane search + update              │
                         │  └─ Callback to bot                    │
                         └─────────────────────────────────────────┘
```

## Workflows

### 1. AI Task Detection (`ai-task-detection.json`)

Анализирует сообщения из чатов и автоматически создаёт задачи в Plane.

**Flow:**
1. Бот отправляет сообщение на `/webhook/ai/detect-task`
2. AI (Llama 3.1 через OpenRouter) анализирует текст
3. Если уверенность ≥75% → автосоздание в Plane
4. Если уверенность 50-74% → запрос подтверждения у админа
5. Callback в бот с результатом

**Webhook Input:**
```json
{
  "source": "telegram_bot",
  "event_type": "message_for_task_detection",
  "message": {
    "text": "Нужно проверить бэкапы на сервере",
    "message_id": 123
  },
  "chat": {
    "id": -1001234567890,
    "title": "IT Support"
  },
  "user": {
    "id": 123456,
    "name": "John",
    "username": "john"
  },
  "plane": {
    "project_id": "uuid",
    "project_name": "HHIVP"
  }
}
```

### 2. AI Voice Report (`ai-voice-report.json`)

Обрабатывает голосовые сообщения и создаёт отчёты о работе.

**Flow:**
1. Бот отправляет URL голосового на `/webhook/ai/voice-report`
2. n8n скачивает файл
3. Whisper транскрибирует (Russian)
4. AI извлекает структурированные данные:
   - Длительность работы
   - Время в дороге
   - Исполнители
   - Компания
   - Описание работ
5. Поиск задачи в Plane по ключевым словам
6. Если найдена → обновление статуса + комментарий
7. Callback в бот с результатом

**Webhook Input:**
```json
{
  "source": "telegram_bot",
  "event_type": "voice_report",
  "voice": {
    "file_url": "https://api.telegram.org/file/bot.../voice.ogg",
    "duration": 45,
    "file_id": "..."
  },
  "admin": {
    "telegram_id": 123456,
    "name": "Admin Name"
  },
  "chat": {
    "id": 123456,
    "type": "private"
  },
  "message_id": 789
}
```

## Установка

### 1. Требования

- n8n (self-hosted или cloud)
- Credentials:
  - **OpenRouter API** - для бесплатных LLM
  - **OpenAI API** - для Whisper (опционально, можно локальный)
  - **Plane API** - для работы с задачами

### 2. Environment Variables в n8n

```bash
# Plane API
PLANE_API_URL=https://plane.hhivp.com
PLANE_WORKSPACE=hhivp

# Webhook Secret (для безопасности)
N8N_WEBHOOK_SECRET=your_secret_here
```

### 3. Credentials в n8n

#### OpenRouter API
- Type: HTTP Header Auth
- Header Name: `Authorization`
- Header Value: `Bearer sk-or-v1-your-key`

#### Plane API
- Type: HTTP Header Auth
- Header Name: `x-api-key`
- Header Value: `plane_api_your-key`

#### OpenAI API (для Whisper)
- Type: OpenAI
- API Key: `sk-your-openai-key`

### 4. Импорт Workflows

1. Открыть n8n
2. Settings → Import from File
3. Выбрать `ai-task-detection.json`
4. Повторить для `ai-voice-report.json`
5. Обновить credentials в каждом workflow
6. Активировать workflows

### 5. Настройка бота

В `.env` бота:
```bash
# n8n Integration
N8N_URL=https://n8n.hhivp.com
N8N_WEBHOOK_SECRET=your_secret_here

# AI Task Detection
AI_TASK_DETECTION_ENABLED=true
AI_TASK_DETECTION_MIN_CONFIDENCE=70
```

## Бесплатные модели OpenRouter

Рекомендуемые модели (бесплатные):

| Model | Скорость | Качество | Использование |
|-------|----------|----------|---------------|
| `meta-llama/llama-3.1-8b-instruct:free` | Быстрая | Хорошее | Task detection |
| `mistralai/mistral-7b-instruct:free` | Быстрая | Хорошее | Extraction |
| `google/gemma-2-9b-it:free` | Средняя | Отличное | Complex tasks |
| `qwen/qwen-2-7b-instruct:free` | Быстрая | Хорошее | Multilingual |

Получить API ключ: https://openrouter.ai/keys

## Тестирование

### Task Detection
```bash
curl -X POST https://n8n.hhivp.com/webhook/ai/detect-task \
  -H "Content-Type: application/json" \
  -d '{
    "message": {"text": "Нужно срочно проверить сервер"},
    "chat": {"id": -100123, "title": "Test"},
    "user": {"id": 123, "name": "Test"},
    "plane": {"project_id": "uuid", "project_name": "Test"}
  }'
```

### Voice Report
```bash
curl -X POST https://n8n.hhivp.com/webhook/ai/voice-report \
  -H "Content-Type: application/json" \
  -d '{
    "voice": {"file_url": "https://...", "duration": 30},
    "admin": {"telegram_id": 123, "name": "Admin"},
    "chat": {"id": 123}
  }'
```

## Troubleshooting

### "OpenRouter rate limit"
- Бесплатные модели имеют лимиты
- Решение: добавить fallback на другую модель или retry

### "Plane API 401"
- Проверить API токен
- Проверить workspace slug

### "Whisper timeout"
- Файл слишком большой (>25MB)
- Решение: уменьшить качество или split

### "Callback failed"
- Бот недоступен
- Проверить что webhook сервер работает
- Проверить firewall

## Расширение

### Добавить новую LLM модель

В node "AI: Analyze Message" изменить `model`:
```json
"model": "anthropic/claude-3-haiku:beta"
```

### Изменить логику детекции

Редактировать system prompt в "AI: Analyze Message" node.

### Добавить уведомления

Добавить Telegram/Slack node после создания задачи.
