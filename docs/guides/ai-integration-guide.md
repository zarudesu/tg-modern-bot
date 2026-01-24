# AI Integration Guide

Руководство по AI интеграции через n8n для автоматической детекции задач и обработки голосовых отчётов.

## Архитектура

```
┌────────────────────┐     ┌─────────────────────────────────────────────┐
│   Telegram Bot     │     │                    n8n                      │
│                    │     │                                             │
│  Chat Monitor ─────┼────►│  AI Task Detection                         │
│  (message_monitor) │     │  ├─ Webhook /ai/detect-task                │
│                    │     │  ├─ OpenRouter AI (Llama 3.1 free)         │
│  Voice Handler ────┼────►│  ├─ Plane API (create issue)               │
│  (voice_transcr.)  │     │  └─ Callback to bot                        │
│                    │     │                                             │
│  ◄─────────────────┼─────┤  AI Voice Report                           │
│  Webhooks:         │     │  ├─ Webhook /ai/voice-report               │
│  /ai/task-result   │     │  ├─ Download voice file                    │
│  /ai/voice-result  │     │  ├─ Whisper transcription                  │
└────────────────────┘     │  ├─ OpenRouter AI (extract data)           │
                           │  ├─ Plane search + update                   │
                           │  └─ Callback to bot                         │
                           └─────────────────────────────────────────────┘
```

## Компоненты системы

### 1. Bot Side

#### Файлы:
| Файл | Назначение |
|------|------------|
| `app/services/n8n_ai_service.py` | Сервис для отправки запросов в n8n |
| `app/handlers/ai_callbacks.py` | Обработка callback кнопок AI |
| `app/handlers/voice_transcription.py` | Обработка голосовых сообщений |
| `app/modules/chat_monitor/message_monitor.py` | Мониторинг сообщений для детекции задач |
| `app/webhooks/server.py` | Webhook endpoints для приёма результатов от n8n |

#### Webhook Endpoints:
| Endpoint | Метод | Назначение |
|----------|-------|------------|
| `/webhooks/ai/task-result` | POST | Результат AI детекции задачи |
| `/webhooks/ai/voice-result` | POST | Результат обработки голосового |

### 2. n8n Side

#### Workflows:
| Workflow | Файл | Назначение |
|----------|------|------------|
| AI Task Detection | `n8n-workflows/ai-task-detection.json` | Детекция задач из сообщений |
| AI Voice Report | `n8n-workflows/ai-voice-report.json` | Обработка голосовых отчётов |

#### Webhook Endpoints в n8n:
| Endpoint | Workflow | Назначение |
|----------|----------|------------|
| `/webhook/ai/detect-task` | AI Task Detection | Приём сообщений для анализа |
| `/webhook/ai/voice-report` | AI Voice Report | Приём голосовых файлов |

## Flows

### Flow 1: AI Task Detection

```
User sends message in monitored group
           │
           ▼
┌─────────────────────────┐
│ Bot: Message Monitor    │
│ (message_monitor.py)    │
└───────────┬─────────────┘
            │ POST to n8n
            ▼
┌─────────────────────────┐
│ n8n: Webhook receive    │
│ /ai/detect-task         │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ n8n: AI Analyze         │
│ (OpenRouter Llama 3.1)  │
└───────────┬─────────────┘
            │ JSON response:
            │ {is_task, confidence, task_data}
            ▼
        ┌───┴───┐
        │       │
   ≥75% │       │ 50-74%
        ▼       ▼
  ┌──────────┐ ┌──────────────┐
  │ Auto-    │ │ Request      │
  │ Create   │ │ Confirmation │
  │ in Plane │ │ from Admin   │
  └────┬─────┘ └──────┬───────┘
       │              │
       └──────┬───────┘
              │ Callback to bot
              ▼
┌─────────────────────────┐
│ Bot: /ai/task-result    │
│ (server.py)             │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Bot: Send notification  │
│ + confirmation buttons  │
│ (ai_callbacks.py)       │
└─────────────────────────┘
```

### Flow 2: AI Voice Report

```
Admin sends voice message
           │
           ▼
┌─────────────────────────┐
│ Bot: Voice Handler      │
│ (voice_transcription.py)│
└───────────┬─────────────┘
            │ POST to n8n (file_url, metadata)
            ▼
┌─────────────────────────┐
│ n8n: Download OGG file  │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ n8n: Whisper API        │
│ (Russian transcription) │
└───────────┬─────────────┘
            │ Transcribed text
            ▼
┌─────────────────────────┐
│ n8n: AI Extract Data    │
│ (OpenRouter)            │
│ - duration_hours        │
│ - travel_hours          │
│ - workers[]             │
│ - company               │
│ - work_description      │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ n8n: Search Plane       │
│ (find task by keywords) │
└───────────┬─────────────┘
            │
            ▼
  ┌─────────┴─────────┐
  │ Found?            │
  └─────────┬─────────┘
       yes  │  no
       ▼    ▼
┌──────────┐ ┌──────────────┐
│ Update   │ │ Return       │
│ task +   │ │ candidates   │
│ comment  │ │ for selection│
└────┬─────┘ └──────┬───────┘
     │              │
     └──────┬───────┘
            │ Callback to bot
            ▼
┌─────────────────────────┐
│ Bot: /ai/voice-result   │
│ (server.py)             │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Bot: Show result +      │
│ task selection keyboard │
│ (ai_callbacks.py)       │
└─────────────────────────┘
```

## Настройка

### 1. Environment Variables (Bot)

```bash
# .env файл бота

# n8n Integration
N8N_URL=https://n8n.hhivp.com
N8N_WEBHOOK_SECRET=your_secret_here

# AI Task Detection
AI_TASK_DETECTION_ENABLED=true
AI_TASK_DETECTION_MIN_CONFIDENCE=70
AI_TASK_DETECTION_RATE_LIMIT=5  # requests per minute

# Webhook server (для приёма результатов)
WEBHOOK_PORT=8080
```

### 2. n8n Credentials

#### OpenRouter API (для бесплатных LLM)
- Type: HTTP Header Auth
- Header Name: `Authorization`
- Header Value: `Bearer sk-or-v1-your-key`
- Получить ключ: https://openrouter.ai/keys

#### Plane API
- Type: HTTP Header Auth
- Header Name: `x-api-key`
- Header Value: `plane_api_your-key`

#### OpenAI API (для Whisper)
- Type: OpenAI
- API Key: `sk-your-openai-key`

### 3. n8n Environment Variables

```bash
# Plane API
PLANE_API_URL=https://plane.hhivp.com
PLANE_WORKSPACE=hhivp

# Webhook Secret (для безопасности)
N8N_WEBHOOK_SECRET=your_secret_here
```

### 4. Import n8n Workflows

1. Открыть n8n Dashboard
2. Settings → Import from File
3. Выбрать `n8n-workflows/ai-task-detection.json`
4. Повторить для `ai-voice-report.json`
5. Обновить credentials в каждом workflow
6. Активировать workflows

## Бесплатные модели OpenRouter

| Model | Скорость | Качество | Рекомендация |
|-------|----------|----------|--------------|
| `meta-llama/llama-3.1-8b-instruct:free` | Быстрая | Хорошее | Task detection |
| `mistralai/mistral-7b-instruct:free` | Быстрая | Хорошее | Data extraction |
| `google/gemma-2-9b-it:free` | Средняя | Отличное | Complex tasks |
| `qwen/qwen-2-7b-instruct:free` | Быстрая | Хорошее | Multilingual |

## API Reference

### Bot → n8n: Task Detection

**Endpoint:** `POST /webhook/ai/detect-task`

**Request:**
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

**Response (immediate):**
```json
{
  "status": "processing",
  "request_id": "uuid"
}
```

### n8n → Bot: Task Detection Result

**Endpoint:** `POST /webhooks/ai/task-result`

**Headers:**
```
X-Webhook-Secret: your_secret_here
Content-Type: application/json
```

**Body:**
```json
{
  "source": "n8n_ai",
  "event_type": "task_detection_result",
  "timestamp": "2025-01-20T12:00:00Z",
  "detection": {
    "is_task": true,
    "confidence": 85,
    "task_data": {
      "title": "Проверить бэкапы на сервере",
      "description": "Необходимо проверить состояние резервных копий",
      "priority": "medium",
      "due_date": null
    },
    "reasoning": "Message contains direct request marker 'нужно' and specific action"
  },
  "original_message": {
    "chat_id": -1001234567890,
    "message_id": 123,
    "text": "Нужно проверить бэкапы на сервере",
    "user_id": 123456,
    "user_name": "John"
  },
  "plane": {
    "project_id": "uuid",
    "project_name": "HHIVP"
  },
  "action_taken": "auto_created",
  "created_issue": {
    "id": "issue-uuid",
    "sequence_id": 456
  }
}
```

### Bot → n8n: Voice Report

**Endpoint:** `POST /webhook/ai/voice-report`

**Request:**
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

### n8n → Bot: Voice Report Result

**Endpoint:** `POST /webhooks/ai/voice-result`

**Headers:**
```
X-Webhook-Secret: your_secret_here
Content-Type: application/json
```

**Body:**
```json
{
  "source": "n8n_ai",
  "event_type": "voice_report_result",
  "timestamp": "2025-01-20T12:00:00Z",
  "success": true,
  "transcription": "Сегодня работали у клиента Харзл...",
  "extraction": {
    "duration_hours": 4,
    "travel_hours": 1,
    "workers": ["Костя", "Саша"],
    "company": "Харзл",
    "work_description": "Установка нового оборудования...",
    "confidence": 0.92
  },
  "plane_tasks": {
    "matched": true,
    "task_id": "issue-uuid",
    "task_title": "Установка оборудования Харзл",
    "updated": true
  },
  "admin": {
    "telegram_id": 123456
  },
  "chat": {
    "id": 123456
  },
  "original_message_id": 789
}
```

## Callback кнопки

### Task Detection Callbacks

| callback_data | Действие |
|---------------|----------|
| `ai_confirm_task:{chat_id}:{msg_id}` | Подтвердить создание задачи |
| `ai_reject_task:{chat_id}:{msg_id}` | Отклонить AI детекцию |
| `ai_edit_task:{chat_id}:{msg_id}` | Редактировать перед созданием |

### Voice Report Callbacks

| callback_data | Действие |
|---------------|----------|
| `voice_select:{admin_id}:{msg_id}:{idx}` | Выбрать задачу из кандидатов |
| `voice_find_task:{admin_id}:{msg_id}` | Ручной поиск задачи |
| `voice_new_task:{admin_id}:{msg_id}` | Создать новую задачу |
| `voice_cancel:{admin_id}:{msg_id}` | Отменить голосовой отчёт |

## Rate Limiting

### Task Detection
- **Default:** 5 requests/minute per chat
- **Configurable:** `AI_TASK_DETECTION_RATE_LIMIT`
- **Behavior:** Excess requests queued or dropped with warning

### Voice Reports
- **Default:** 2 requests/minute per admin
- **File size limit:** 25 MB (Whisper API)
- **Duration limit:** 5 minutes recommended

## Troubleshooting

### "OpenRouter rate limit"
**Проблема:** Бесплатные модели имеют ограничения
**Решение:**
1. Добавить fallback на другую модель в n8n workflow
2. Увеличить интервал между запросами
3. Использовать платный tier

### "Plane API 401"
**Проблема:** Неверный API токен
**Решение:**
1. Проверить токен в n8n credentials
2. Убедиться что токен имеет права на workspace
3. Проверить workspace slug в environment

### "Whisper timeout"
**Проблема:** Файл слишком большой
**Решение:**
1. Уменьшить качество аудио перед отправкой
2. Разбить длинные записи на части
3. Увеличить timeout в n8n node

### "Callback failed"
**Проблема:** Бот не получает результаты от n8n
**Решение:**
1. Проверить что webhook server запущен: `curl http://localhost:8080/health`
2. Проверить firewall/NAT для внешнего доступа
3. Проверить `X-Webhook-Secret` header
4. Посмотреть логи: `make bot-logs | grep webhook`

### "No tasks detected"
**Проблема:** AI не детектирует задачи
**Решение:**
1. Проверить минимальную длину сообщения (>10 символов)
2. Проверить confidence threshold в настройках
3. Изменить system prompt в n8n workflow

## Security

### Webhook Authentication
Все webhooks ОБЯЗАТЕЛЬНО должны проверять `X-Webhook-Secret`:

```python
# server.py
async def ai_task_result(request):
    secret = request.headers.get('X-Webhook-Secret')
    if secret != settings.n8n_webhook_secret:
        return web.json_response(
            {"error": "Unauthorized"},
            status=401
        )
```

### Rate Limiting
Защита от спама в `n8n_ai_service.py`:

```python
class N8nAIService:
    def __init__(self):
        self._rate_limiter = {}

    async def check_rate_limit(self, chat_id: int) -> bool:
        # Max 5 requests per minute
        ...
```

### Data Privacy
- Голосовые файлы не сохраняются после обработки
- Транскрипции хранятся только в кэше (TTL 15 минут)
- Персональные данные не логируются

## Мониторинг

### Метрики для отслеживания
- `ai_detection_requests_total` - всего запросов детекции
- `ai_detection_success_rate` - % успешных детекций
- `ai_voice_processing_time` - время обработки голосовых
- `n8n_callback_latency` - задержка callback от n8n

### Логирование
Все AI операции логируются с тегом `[AI]`:
```bash
make bot-logs | grep "\[AI\]"
```

---

**Last Updated:** 2026-01-23
**Version:** 1.0
**Related:**
- [Task Reports Guide](task-reports-guide.md)
- [n8n Workflows README](../../n8n-workflows/README.md)
