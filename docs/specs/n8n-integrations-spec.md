# n8n Integrations Specification

> **Status:** Planning
> **Created:** 2026-01-20
> **Owner:** Development Team

---

## Overview

This document specifies planned n8n workflow integrations for voice processing, AI report generation, and automated summaries.

---

## 1. Voice Transcription Workflow

### Purpose
Allow users to send voice messages that get transcribed via AI and optionally converted to tasks or reports.

### Flow Diagram
```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   User      │     │   Bot       │     │   n8n       │     │   OpenAI    │
│ Voice Msg   │────▶│ Receives    │────▶│ Workflow    │────▶│ Whisper API │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                           │                   │                    │
                           │                   │◀───────────────────┘
                           │◀──────────────────┘    Transcription
                           │
                    ┌──────▼──────┐
                    │ User sees   │
                    │ transcription│
                    │ + actions   │
                    └─────────────┘
```

### Bot Implementation

**File:** `app/handlers/voice_handler.py`

```python
from aiogram import Router
from aiogram.types import Message
from ..services.n8n_integration_service import n8n_service

router = Router()

@router.message(F.voice)
async def handle_voice_message(message: Message):
    """Handle voice messages for transcription"""
    # 1. Get voice file
    file = await message.bot.get_file(message.voice.file_id)
    file_url = f"https://api.telegram.org/file/bot{settings.telegram_token}/{file.file_path}"

    # 2. Send to n8n for transcription
    await message.reply("🎤 Обрабатываю голосовое сообщение...")

    result = await n8n_service.send_voice_for_transcription(
        file_url=file_url,
        user_id=message.from_user.id,
        chat_id=message.chat.id,
        duration=message.voice.duration
    )

    if result.success:
        # 3. Show transcription with action buttons
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Создать задачу", callback_data=f"voice_task:{result.request_id}")],
            [InlineKeyboardButton(text="📋 Создать отчет", callback_data=f"voice_report:{result.request_id}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="voice_cancel")]
        ])

        await message.reply(
            f"📝 *Распознанный текст:*\n\n{result.transcription}",
            reply_markup=keyboard,
            parse_mode="MarkdownV2"
        )
    else:
        await message.reply(f"❌ Ошибка распознавания: {result.error}")
```

### n8n Workflow Specification

**Workflow Name:** `voice-transcription`
**Trigger:** Webhook POST `/webhook/voice-transcribe`

**Input Schema:**
```json
{
  "file_url": "https://api.telegram.org/file/bot.../voice.oga",
  "user_id": 28795547,
  "chat_id": -1001234567890,
  "duration": 15,
  "request_id": "uuid-v4",
  "timestamp": "2026-01-20T10:30:00Z"
}
```

**Workflow Steps:**

1. **Webhook Trigger** - Receive request
2. **HTTP Request** - Download voice file from Telegram
3. **HTTP Request** - Send to OpenAI Whisper API
   ```
   POST https://api.openai.com/v1/audio/transcriptions
   Headers: Authorization: Bearer ${OPENAI_API_KEY}
   Body: multipart/form-data with file and model="whisper-1"
   ```
4. **Respond to Webhook** - Return transcription

**Output Schema:**
```json
{
  "success": true,
  "request_id": "uuid-v4",
  "transcription": "Распознанный текст голосового сообщения",
  "language": "ru",
  "duration_processed": 15,
  "confidence": 0.95
}
```

**Error Response:**
```json
{
  "success": false,
  "request_id": "uuid-v4",
  "error": "Audio file too short or unclear",
  "error_code": "TRANSCRIPTION_FAILED"
}
```

### Environment Variables

```bash
# .env additions
VOICE_TRANSCRIPTION_ENABLED=true
VOICE_MAX_DURATION=120  # seconds
VOICE_WEBHOOK_URL=https://n8n.hhivp.com/webhook/voice-transcribe
```

---

## 2. AI Report Generation Workflow

### Purpose
Automatically generate formatted work reports from task data using AI.

### Flow Diagram
```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Task Done   │     │   Bot       │     │   n8n       │     │  Claude/GPT │
│ in Plane    │────▶│ Collects    │────▶│ Workflow    │────▶│     API     │
└─────────────┘     │ task data   │     └─────────────┘     └─────────────┘
                    └─────────────┘            │                    │
                           │                   │◀───────────────────┘
                           │◀──────────────────┘    Generated report
                           │
                    ┌──────▼──────┐
                    │ Admin sees  │
                    │ draft report│
                    │ for review  │
                    └─────────────┘
```

### Bot Implementation

**File:** `app/services/ai_report_service.py`

```python
class AIReportService:
    """Service for AI-powered report generation"""

    async def generate_report_from_task(
        self,
        task_report: TaskReport,
        include_comments: bool = True
    ) -> AIGeneratedReport:
        """Generate formatted report using AI"""

        # 1. Collect task data
        task_data = {
            "title": task_report.plane_issue_title,
            "description": task_report.plane_issue_description,
            "project": task_report.project_name,
            "assignees": task_report.workers,
            "comments": task_report.plane_comments if include_comments else [],
            "duration_minutes": task_report.duration,
            "company": task_report.company_name
        }

        # 2. Send to n8n for AI processing
        result = await n8n_service.generate_report(task_data)

        return AIGeneratedReport(
            summary=result.summary,
            work_description=result.work_description,
            recommendations=result.recommendations,
            formatted_report=result.formatted_report
        )
```

### n8n Workflow Specification

**Workflow Name:** `generate-report`
**Trigger:** Webhook POST `/webhook/generate-report`

**Input Schema:**
```json
{
  "task_data": {
    "title": "Настройка почтового сервера",
    "description": "Клиент жаловался на проблемы с почтой...",
    "project": "HHIVP",
    "assignees": ["Константин", "Дмитрий"],
    "comments": [
      {"author": "Client", "text": "Почта не работает с утра"},
      {"author": "Admin", "text": "Перезапустил сервис, проверьте"}
    ],
    "duration_minutes": 45,
    "company": "ООО Рога и Копыта"
  },
  "report_style": "formal",
  "language": "ru",
  "request_id": "uuid-v4"
}
```

**AI Prompt Template:**
```
Ты — IT-специалист, составляющий отчет о выполненной работе для клиента.

Данные задачи:
- Название: {title}
- Описание: {description}
- Компания: {company}
- Исполнители: {assignees}
- Время работы: {duration_minutes} минут

Комментарии по задаче:
{comments}

Составь краткий профессиональный отчет о выполненной работе:
1. Краткое описание проблемы (1-2 предложения)
2. Что было сделано (2-3 пункта)
3. Результат (1 предложение)

Стиль: деловой, на русском языке.
```

**Output Schema:**
```json
{
  "success": true,
  "request_id": "uuid-v4",
  "report": {
    "problem_summary": "Клиент обратился с проблемой...",
    "work_done": [
      "Проведена диагностика почтового сервера",
      "Перезапущен сервис SMTP",
      "Проверена доставка тестовых писем"
    ],
    "result": "Почтовый сервер восстановлен, работает штатно.",
    "formatted_text": "Полный отформатированный текст отчета..."
  },
  "tokens_used": 450,
  "model": "gpt-4-turbo"
}
```

---

## 3. Daily Summary Workflow

### Purpose
Generate daily summary of completed tasks and send to team chat.

### Flow Diagram
```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Scheduled   │     │   n8n       │     │  Database   │     │  Claude/GPT │
│ 18:00 daily │────▶│ Workflow    │────▶│ Query tasks │────▶│ Summarize   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                                               │                    │
                                               │                    │
                    ┌─────────────┐            │                    │
                    │  Telegram   │◀───────────┴────────────────────┘
                    │   Group     │         Summary message
                    └─────────────┘
```

### n8n Workflow Specification

**Workflow Name:** `daily-summary`
**Trigger:** Cron `0 18 * * 1-5` (18:00 Mon-Fri)

**Steps:**

1. **Schedule Trigger** - 18:00 daily
2. **PostgreSQL Query** - Get today's completed tasks
   ```sql
   SELECT
     tr.id,
     tr.plane_issue_title,
     tr.company_name,
     tr.workers,
     tr.duration,
     tr.approved_at
   FROM task_reports tr
   WHERE tr.status = 'sent'
     AND DATE(tr.approved_at) = CURRENT_DATE
   ORDER BY tr.approved_at;
   ```
3. **IF** - Check if any tasks completed
4. **HTTP Request** - Send to AI for summary
5. **Telegram Bot API** - Send message to group

**Output Message Format:**
```
📊 Итоги дня: 20 января 2026

Выполнено задач: 5
Общее время: 4 часа 30 минут

🏢 По компаниям:
• ООО Рога и Копыта — 2 задачи (1ч 45м)
• ИП Иванов — 2 задачи (2ч 15м)
• ООО Дельта — 1 задача (30м)

👥 По исполнителям:
• Константин — 3 задачи
• Дмитрий — 2 задачи

📝 Краткое описание:
Основная работа — настройка серверного оборудования
и решение проблем с почтовыми сервисами клиентов.

Хорошего вечера! 🌙
```

---

## 4. Webhook Security Implementation

### Signature Verification

All webhooks MUST implement HMAC signature verification.

**Bot Side (receiving webhooks from n8n):**

```python
# app/webhooks/security.py
import hmac
import hashlib

def verify_webhook_signature(
    payload: bytes,
    signature: str,
    secret: str
) -> bool:
    """Verify n8n webhook signature"""
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(f"sha256={expected}", signature)
```

**n8n Side (sending webhooks to bot):**

Configure in n8n HTTP Request node:
```
Headers:
  X-Webhook-Signature: ={{ $json.signature }}
  Content-Type: application/json
```

Compute signature in Code node:
```javascript
const crypto = require('crypto');
const secret = $env.WEBHOOK_SECRET;
const payload = JSON.stringify($json);
const signature = 'sha256=' + crypto
  .createHmac('sha256', secret)
  .update(payload)
  .digest('hex');

return { ...$json, signature };
```

---

## 5. Error Handling

### Retry Strategy

All n8n workflows should implement:

1. **Automatic Retry** - 3 attempts with exponential backoff
2. **Dead Letter Queue** - Failed requests logged to database
3. **Alert on Failure** - Telegram notification to admin group

### Error Codes

| Code | Description | Action |
|------|-------------|--------|
| `VOICE_TOO_SHORT` | Voice < 1 second | Inform user |
| `VOICE_TOO_LONG` | Voice > 120 seconds | Inform user |
| `TRANSCRIPTION_FAILED` | Whisper API error | Retry 3x |
| `AI_GENERATION_FAILED` | GPT/Claude error | Retry 3x |
| `RATE_LIMIT_EXCEEDED` | API rate limit | Backoff 60s |
| `WEBHOOK_TIMEOUT` | n8n didn't respond | Retry 3x |

---

## 6. Environment Variables

Add to `.env.example`:

```bash
# Voice Transcription
VOICE_TRANSCRIPTION_ENABLED=false
VOICE_MAX_DURATION=120
VOICE_WEBHOOK_URL=

# AI Report Generation
AI_REPORT_GENERATION_ENABLED=false
AI_REPORT_WEBHOOK_URL=
AI_REPORT_MODEL=gpt-4-turbo

# Daily Summary
DAILY_SUMMARY_ENABLED=false
DAILY_SUMMARY_CHAT_ID=
DAILY_SUMMARY_TIME=18:00

# Webhook Security
N8N_WEBHOOK_SECRET=generate-strong-secret-here
```

---

## 7. Database Schema Additions

```sql
-- Migration: add_voice_transcriptions
CREATE TABLE voice_transcriptions (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    chat_id BIGINT NOT NULL,
    file_id VARCHAR(255) NOT NULL,
    duration INTEGER NOT NULL,
    transcription TEXT,
    language VARCHAR(10),
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT
);

CREATE INDEX idx_voice_user ON voice_transcriptions(user_id);
CREATE INDEX idx_voice_status ON voice_transcriptions(status);

-- Migration: add_ai_generated_reports
CREATE TABLE ai_generated_reports (
    id SERIAL PRIMARY KEY,
    task_report_id INTEGER REFERENCES task_reports(id),
    generated_text TEXT NOT NULL,
    model_used VARCHAR(50),
    tokens_used INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    approved BOOLEAN DEFAULT FALSE,
    approved_by BIGINT
);
```

---

## 8. Testing Plan

### Unit Tests

```python
# tests/test_voice_handler.py
async def test_voice_message_triggers_transcription():
    """Voice message should be sent to n8n for transcription"""
    pass

async def test_voice_too_long_rejected():
    """Voice > 120s should be rejected immediately"""
    pass

# tests/test_ai_report_service.py
async def test_report_generation_with_comments():
    """Report should include task comments in AI prompt"""
    pass

async def test_report_generation_timeout():
    """Service should handle n8n timeout gracefully"""
    pass
```

### Integration Tests

1. Send voice message → verify transcription returned
2. Complete task → verify AI report generated
3. Wait for 18:00 → verify daily summary sent

### Load Tests

- 10 concurrent voice messages
- 50 concurrent report generations
- Verify n8n doesn't get overwhelmed

---

## Changelog

### 2026-01-20: Initial Specification
- Voice transcription workflow defined
- AI report generation workflow defined
- Daily summary workflow defined
- Security requirements documented
- Database schema additions specified
