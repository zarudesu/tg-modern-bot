# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## MCP Tools
**Перед выбором инструмента спроси `mcp-compass`** — он порекомендует оптимальный MCP для задачи.

---

## 🚦 Session Continuity (READ FIRST!)

> **For new sessions, compact mode, or resuming work — start here!**

### Before Starting Work

```bash
# 1. Check current roadmap & issues
cat docs/ROADMAP.md | grep -A2 "Status:"

# 2. Check recent commits
git log --oneline -5

# 3. Check if tests pass
python3 test_modules_isolation.py && python3 test_basic.py
```

### Current Priority (2026-01-20)

**Phase 1: Critical Fixes (IN PROGRESS)**
- [ ] Event Bus memory leak (`app/core/events/event_bus.py:135`)
- [ ] Webhook error exposure (`app/webhooks/server.py:355`)
- [ ] Webhook signature required (`app/webhooks/server.py:65`)
- [ ] Google Sheets blocking I/O (`app/integrations/google_sheets.py:49`)
- [ ] aiohttp session reuse (`app/services/n8n_integration_service.py:104`)

**See full details:** [`docs/ROADMAP.md`](docs/ROADMAP.md)

### After Completing Work

```bash
# 1. Run tests
python3 test_modules_isolation.py
python3 test_basic.py

# 2. Update ROADMAP.md status (mark [x] completed)

# 3. Commit with convention
git add -A
git commit -m "fix(scope): description"

# 4. If deploying
./deploy.sh full
```

### Commit Convention
```
fix(webhook): Remove error details from response
feat(n8n): Add voice transcription webhook
refactor(services): Implement dependency injection
docs: Update roadmap after Phase 1
```

---

## 📑 Table of Contents

- [Session Continuity](#-session-continuity-read-first)
- [Quick Start](#-quick-start)
- [Essential Commands](#-essential-commands)
- [Module Status Dashboard](#-module-status-dashboard)
- [Known Issues & Technical Debt](#-known-issues--technical-debt)
- [Architecture Overview](#-architecture-overview)
- [Development Guide](#-development-guide)
- [n8n Integration Plans](#-n8n-integration-plans)
- [Configuration](#-configuration)
- [Security & Credentials](#-security--credentials)
- [Debugging](#-debugging)
- [Testing Strategy](#-testing-strategy)
- [References](#-references)

---

## 🚀 Quick Start

### First Time Setup
```bash
cd /Users/zardes/Projects/tg-mordern-bot

# Create .env from example
cp .env.example .env
# Add your token: TELEGRAM_TOKEN=your_token

# Start database + bot
make dev
```

### If Already Running

**⚠️ IMPORTANT: Choose correct workflow based on your setup!**

#### 📍 Local Development (bot_manager.sh)
```bash
make dev-restart  # Fast restart (reloads code automatically)
make bot-logs     # View logs
```

#### 🐳 Docker Development (code INSIDE container)

**✅ RECOMMENDED: Use Makefile commands**
```bash
# After code changes - FULL REBUILD (slow but guaranteed)
make bot-rebuild-clean    # Only bot (DB must be running)
make full-rebuild-clean   # Full stack (DB + Redis + Bot)

# View logs
make bot-logs
# Or: make full-logs
```

**Manual Docker commands (if needed):**
```bash
# Option 1: Full rebuild (SAFEST after code changes)
docker-compose build --no-cache telegram-bot
docker-compose up -d --force-recreate telegram-bot

# Option 2: Faster rebuild (uses cache for unchanged layers)
docker-compose build telegram-bot
docker-compose up -d --force-recreate telegram-bot

# View logs
docker-compose logs -f telegram-bot
# Or: docker logs telegram-bot-app-full -f
```

**❌ WRONG - will NOT apply code changes:**
```bash
docker-compose restart telegram-bot        # Only restarts OLD container ❌
docker-compose build telegram-bot          # Builds image but doesn't update container ❌
docker-compose up -d telegram-bot          # Uses EXISTING container if running ❌
```

**Why `--force-recreate`?**
- Our `docker-compose.yml` does NOT mount code as volume (only logs & .env)
- Code is **baked into Docker image** during build
- `restart` = restart old container with old code
- `up -d --force-recreate` = delete old container + create new from fresh image

**Quick Reference:**
| Scenario | Command |
|----------|---------|
| Changed Python code | `make bot-rebuild-clean` or `make full-rebuild-clean` |
| Changed requirements.txt | `make bot-rebuild-clean` (needs --no-cache) |
| Changed .env only | `docker-compose restart telegram-bot` (OK) |
| Changed docker-compose.yml | `docker-compose up -d --force-recreate telegram-bot` |

---

## ⚡ Essential Commands

### Development Workflow
```bash
# Local development (fastest, code auto-reload)
make dev                          # Start database + bot
make dev-restart                  # Restart bot only (FAST)
make dev-stop                     # Stop everything

# Docker development (code changes require rebuild)
make bot-rebuild-clean            # Rebuild bot after code changes
make full-rebuild-clean           # Rebuild full stack after code changes

# Monitoring
make bot-logs                     # View bot logs (most common)
make bot-status                   # Check bot status
make db-shell                     # PostgreSQL console

# Code quality
make format                       # Format with black and flake8
make typecheck                    # Run mypy
make test                         # Run basic tests
```

### Database Management
```bash
make db-up                        # Start PostgreSQL + Redis only
make db-down                      # Stop database
make db-backup                    # Create backup
```

### Testing
```bash
python3 test_basic.py             # Basic functionality
python3 test_modules_isolation.py # Module isolation (CRITICAL!)
python3 test_email_fix.py         # Email filter tests
```

### Production Deployment

**⚡ NEW: Use `deploy.sh` script for all production deployments**

```bash
# Full deployment (after code changes)
./deploy.sh full              # push + pull + build + rebuild + logs

# Quick deployment (minor changes, no rebuild)
./deploy.sh quick             # push + pull + restart + logs

# Individual commands
./deploy.sh push              # Push to GitHub
./deploy.sh pull              # Pull on server
./deploy.sh build             # Rebuild Docker image
./deploy.sh rebuild           # Rebuild and restart container
./deploy.sh restart           # Just restart (for .env changes)
./deploy.sh logs              # View bot logs
./deploy.sh status            # Check container status

# Options
./deploy.sh full --no-cache   # Force clean build (slow but safe)
./deploy.sh logs --tail 100   # Show last 100 log lines
```

**Manual Commands (if needed):**
```bash
# SSH access (passwordless with RSA key)
ssh hhivp@rd.hhivp.com            # Connect to production server

# Deployment
cd /opt/tg-modern-bot && git pull origin main  # Pull latest code
docker-compose -f docker-compose.prod.yml build --no-cache bot  # Rebuild
docker stop hhivp-bot-app-prod && docker rm hhivp-bot-app-prod  # Remove old
docker-compose -f docker-compose.prod.yml up -d bot  # Start new

# Monitoring
docker logs hhivp-bot-app-prod --tail 100 -f  # View logs
docker ps --filter name=hhivp-bot  # Check containers
curl http://localhost:8083/health  # Webhook health (bot runs on 8083)
```

**Production Notes:**
- Bot webhook runs on **port 8083** (external) → 8080 (internal)
- n8n workflows send webhooks to: `http://rd.hhivp.com:8083/webhooks/task-completed`
- PostgreSQL container: `e30e3f83b282_hhivp-bot-postgres-prod`
- Database queries: `docker exec e30e3f83b282_hhivp-bot-postgres-prod psql -U hhivp_bot -d hhivp_bot_prod -c "..."`
- SSH key: `~/.ssh/id_rsa` (4096-bit RSA, passwordless authentication)

---

## 📊 Module Status Dashboard

| Module | Status | Location | Documentation |
|--------|--------|----------|---------------|
| **Task Reports** | ✅ PRODUCTION | `app/modules/task_reports/` | [`docs/guides/task-reports-guide.md`](docs/guides/task-reports-guide.md) |
| **Support Requests** | ✅ PRODUCTION | `app/modules/chat_support/` | [`docs/guides/support-requests-guide.md`](docs/guides/support-requests-guide.md) |
| **Voice Transcription** | ✅ PRODUCTION | `app/handlers/voice_transcription.py` | Voice → AI → Work Journal (FREE APIs) |
| **Daily Tasks** | ✅ PRODUCTION | `app/modules/daily_tasks/` | Email → Plane.so automation |
| **Work Journal** | ✅ PRODUCTION | `app/modules/work_journal/` | Work entries → Google Sheets |
| **AI Assistant** | 🚧 BETA | `app/modules/ai_assistant/` | OpenAI/Anthropic integration |
| **Chat Monitor** | ✅ PRODUCTION | `app/modules/chat_monitor/` | Persistent context + Problem detection |
| **Chat AI Analysis** | ✅ PRODUCTION | `app/services/` | Summary + Problem detection + Context |

### Task Reports Module (PRODUCTION READY)

**Purpose:** Automated client reporting when support tasks completed in Plane.so

**Quick Flow:**
```
Plane task "Done" → n8n webhook → Bot notification → Admin fills report →
Client receives + Google Sheets + Group notification
```

**Key Features:**
- ✅ Auto-fills task data from Plane (title, description, assignees)
- ✅ Independent field editing (duration, travel, company, workers)
- ✅ Company mapping (15+ companies: Plane project → Russian names)
- ✅ Workers autofill from Plane assignees
- ✅ Complete integration: client chat + work_journal + Google Sheets + group notification
- ✅ **Voice Fill** - заполнение отчёта голосом с детекцией конфликтов

**Voice Fill (NEW!):**

Вместо ручного ввода можно отправить голосовое:
```
«2 часа, выезд, Дима и Костя, настроили принтер и обновили ПО»
```

**Как работает:**
1. Admin нажимает "📝 Заполнить отчёт"
2. Отправляет голосовое (или текст)
3. AI извлекает: длительность, тип работы, исполнителей, описание
4. Если данные расходятся с Plane — показывает UI для выбора
5. Применяет данные и показывает превью

**Детекция конфликтов:**
- Сравнивает компанию из голоса vs Plane project
- Сравнивает исполнителей из голоса vs Plane assignees
- Если отличаются — кнопки выбора "🎤 Голос" или "✈️ Plane"

**Файлы:**
- `app/modules/task_reports/handlers/voice_fill.py` - Voice fill handler
- `app/modules/task_reports/handlers/creation.py` - Shows voice hint

**Recent Fixes:**
- BUG #5 (2025-10-08): `approve_send` now creates work_journal + Google Sheets sync

**📚 Full Documentation:** [`docs/guides/task-reports-guide.md`](docs/guides/task-reports-guide.md)

---

### Support Requests Module (PRODUCTION READY)

**Purpose:** Allow users to create support requests from group chats → auto-creates tasks in Plane.so

**Quick Flows:**

**Flow 1: User Creates Request**
```
User runs /request in group → Types problem description →
Bot creates Plane task + notifies admins → User gets ticket number
```

**Flow 2: Create Task from Any Message (NEW!)**
```
User sees problem in group message → Anyone replies with /task →
Bot creates Plane task with original author as owner + full context
```

**Key Features:**
- ✅ Simple user flow: `/request` → type problem → done
- ✅ **NEW:** `/task` command - create tasks from any message via reply
- ✅ Auto-creates tasks in Plane with full user context
- ✅ Maps group chats to specific Plane projects
- ✅ Notifies admins about new requests
- ✅ FSM-based state management (no message conflicts)
- ✅ 10-minute timeout for `/request` flow (prevents hanging states)

**User Commands:**
- `/request` - Create new support request (FSM flow)
- `/task [comment]` - Reply to any message to create task (instant)

**Admin Commands:**
- `/setup_chat` - Configure group for support requests
- `/list_chats` - List all configured groups
- `/remove_chat` - Remove group configuration

**Setup Required:**
- Admin runs `/setup_chat` in group to map to Plane project
- Users can then create requests with `/request` or `/task`

**`/task` Command Details:**
- **Usage:** Reply to any message + `/task [optional comment]`
- **Available to:** All users (not just admins)
- **Priority:** Always medium
- **Task title:** Auto-generated from first 50 characters
- **Task owner:** Original message author
- **Context saved in Plane comment:**
  - Original author info (name, username, ID)
  - Creator info (who used `/task`)
  - Message link (for public/private groups)
  - Optional additional comment
  - Chat name and timestamp
- **Admin notification:** Shows 🎯 icon (vs ✅ for `/request`)

**Example `/task` Usage:**
```
User A: "Сервер не отвечает, нужна помощь"
User B: /task Высокий приоритет, проверьте ASAP
Bot: ✅ Задача создана в Plane (автор: User A, создал: User B)
```

**Current Status:**
- ✅ Module loaded and active (main.py:273-275)
- ✅ `/request` flow with FSM + 10-minute timeout
- ✅ `/task` command for quick task creation from messages
- ⚠️ No chat mappings configured yet (run `/setup_chat` first)

**📚 Full Documentation:** [`docs/guides/support-requests-guide.md`](docs/guides/support-requests-guide.md)

---

### Chat AI Analysis Module (PRODUCTION READY)

**Purpose:** AI-powered analysis of group chat messages for problem detection, summarization, and context tracking.

**Architecture:**
```
Messages → ChatContextService (DB) → ProblemDetector → Alert to Group
                                  → SummaryService → /ai_summary command
```

**Key Components:**

| Component | File | Purpose |
|-----------|------|---------|
| `ChatContextService` | `app/services/chat_context_service.py` | Persistent message storage in PostgreSQL |
| `ProblemDetectorService` | `app/services/problem_detector_service.py` | Keyword + AI problem detection |
| `SummaryService` | `app/services/summary_service.py` | AI-powered chat summarization |
| `ChatMessage` | `app/database/chat_ai_models.py` | SQLAlchemy model for messages |
| `ChatAISettings` | `app/database/chat_ai_models.py` | Per-chat AI configuration |
| `DetectedIssue` | `app/database/chat_ai_models.py` | Tracked problems/issues |

**Database Tables (Migration 009):**
- `chat_messages` - Persistent message history with AI analysis fields
- `chat_ai_settings` - Per-chat configuration (context size, feature toggles)
- `detected_issues` - Tracked problems with status workflow

**AI Commands (Admin only):**
```
/ai_summary [N]     - Generate summary of last N messages (default: 100)
/ai_daily           - Generate daily summary
/ai_problems        - Show open detected problems
/ai_settings        - View/change AI settings for chat
/monitor_status     - Show monitoring statistics
```

**AI Settings Management:**
```
/ai_settings problem_detection on/off  - Toggle problem detection
/ai_settings daily_summary on/off      - Toggle daily summaries
/ai_settings context_size 100          - Set context window size
```

**Problem Detection:**
- **Keyword matching** - Russian problem keywords ("не работает", "сломалось", "ошибка", etc.)
- **Question patterns** - Detects unanswered questions
- **Urgency boosters** - "срочно", "!!!", CAPS detection
- **AI semantic analysis** - Uses OpenRouter for context-aware detection
- **Rate limiting** - 60 seconds cooldown per chat

**Message Storage:**
- All group messages stored in `chat_messages` table
- Configurable context size (default: 100 messages)
- Long-term history preserved
- AI analysis fields: sentiment, is_question, intent

**Current Status:**
- ✅ Persistent context storage (ChatContextService)
- ✅ Problem detection with AI (ProblemDetectorService)
- ✅ Summary generation (SummaryService)
- ✅ Admin commands (/ai_summary, /ai_settings, /ai_problems)
- ✅ Alerts sent to group chat (as replies)

---

### Voice Transcription Module (PRODUCTION READY)

**Purpose:** Voice-to-text transcription with AI extraction of work report data using FREE APIs

**Quick Flow:**
```
Admin sends voice message → HuggingFace Whisper (FREE) → Transcription →
OpenRouter AI (FREE) → Extract structured data → Match to DB →
Create Work Journal entries
```

**Key Features:**
- ✅ **FREE transcription** via HuggingFace Whisper API (no cost!)
- ✅ **FREE AI extraction** via OpenRouter (Mistral/Llama models)
- ✅ **Multi-entry support** - record full day report in single voice message
- ✅ **DB matching** - AI matches companies/workers to database values
- ✅ **Data validation** - extracted fields match WorkJournalEntry schema

**How It Works:**

1. **Voice → Text (HuggingFace Whisper)**
   - Uses `openai/whisper-large-v3` model
   - Endpoint: `https://router.huggingface.co/hf-inference/models/openai/whisper-large-v3`
   - Supports OGG/WAV audio formats
   - FREE with HuggingFace API key

2. **Text → Structured Data (OpenRouter AI)**
   - Uses FREE model: `mistralai/devstral-2512:free`
   - Extracts: work_duration, is_travel, workers, company, work_description
   - Fetches valid values from database for matching
   - **Company aliases** for voice recognition (сленг → официальное название)

3. **Multi-Entry Support**
   - Single voice message can contain multiple work entries
   - AI returns `{entries: [...]}` with array of entries
   - Each entry displayed separately with "Create Task" button

**Example Voice Message:**
```
"Сегодня работали с Костей у Харизмы. Настраивали камеры,
заняло 4 часа. Потом ездили в Дельту на 2 часа чинить принтер."
```

**AI Extracts:**
```json
{
  "entries": [
    {
      "work_duration": "4ч",
      "is_travel": false,
      "workers": ["Костя"],
      "company": "Харц Лабз",  // "харизма" → "Харц Лабз"
      "work_description": "Настройка камер видеонаблюдения"
    },
    {
      "work_duration": "2ч",
      "is_travel": true,
      "workers": ["Костя"],
      "company": "Дельта",
      "work_description": "Ремонт принтера"
    }
  ]
}
```

**Company Aliases (voice → official name):**

| Голосом | → В БД |
|---------|--------|
| "харизма", "хардслабс", "харц" | Харц Лабз |
| "софтфабрик", "фабрик" | СофтФабрик |
| "3д ру", "тридиру", "дыра" | 3Д.РУ |
| "сад", "здоровье" | Сад Здоровья |
| "дельта телеком" | Дельта |
| "штифтер" | Стифтер |
| "сосновка" | Сосновый бор |
| "вёшки", "вешки" | Вёшки 95 |
| "вондига" | Вондига Парк |
| "цифра" | ЦифраЦифра |
| "хивп", "эйчхивп" | HHIVP |

**Unmatched Names:**

Если компания/работник не найден в БД:
- AI всё равно возвращает упомянутое имя
- Добавляет флаг `company_unmatched: true` или `workers_unmatched: ["Имя"]`
- В UI показывается ⚠️ предупреждение
- Пользователь может использовать как есть или выбрать из списка

**Required Environment Variables:**
```bash
# HuggingFace (FREE transcription)
HUGGINGFACE_API_KEY=hf_xxxxxxxxxxxxx

# OpenRouter (FREE AI extraction)
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxx
```

**File:** `app/handlers/voice_transcription.py`

**Key Functions:**
- `transcribe_audio()` - HuggingFace Whisper transcription
- `extract_report_data_with_ai()` - OpenRouter AI extraction
- `get_valid_companies_and_workers()` - Fetch DB values for matching
- `handle_voice_message()` - Main handler for voice messages

**Current Status:**
- ✅ Transcription works (HuggingFace Whisper)
- ✅ AI extraction works (OpenRouter free model)
- ✅ Multi-entry support implemented
- ✅ DB matching for companies/workers
- ✅ Company aliases for voice recognition
- ✅ Unmatched name warnings with preview
- ✅ Voice Fill for TaskReports with conflict detection

---

## ⚠️ Known Issues & Technical Debt

> **Full details:** [`docs/ROADMAP.md`](docs/ROADMAP.md)

### Critical (Fix Immediately)

| Issue | File | Impact |
|-------|------|--------|
| Event Bus memory leak | `app/core/events/event_bus.py:135` | ~360 MB/month growth |
| Webhook exposes errors | `app/webhooks/server.py:355` | Security: stack trace leak |
| Webhook verification optional | `app/webhooks/server.py:65` | Security: spoofed webhooks |
| Google Sheets blocking | `app/integrations/google_sheets.py:49` | 1-5s event loop block |
| aiohttp new session/request | `app/services/n8n_integration_service.py:104` | 3-5x slower API calls |

### Architecture Issues

| Issue | Impact | Solution |
|-------|--------|----------|
| Global singletons | Untestable, fragile init | Dependency Injection |
| Hardcoded Telegram IDs | `task_reports_service.py:28-100` | Move to database |
| N+1 queries | Performance | Use `selectinload()` |
| Rate limiting not implemented | DoS vulnerability | Add middleware |
| DB pool size=5 | Connection exhaustion | Increase to 20 |

### Performance Limits

- **Current capacity:** ~100 concurrent users
- **Memory growth:** ~360 MB/month (event history)
- **API latency:** 3-5x slower due to session recreation

---

## 🔗 n8n Integration

### n8n Access
- **URL:** https://n8n.hhivp.com
- **API:** `curl -H "X-N8N-API-KEY: $N8N_API_KEY" https://n8n.hhivp.com/api/v1/workflows`
- **API Key:** In `.env` as `N8N_API_KEY` (JWT token)

### Active Workflows (Production)

| ID | Workflow | Для бота? | Описание |
|----|----------|-----------|----------|
| `lrn3RNMYCeJlvad9` | **TG bot → Google Sheets** | ✅ ДА | Bot отправляет task reports → n8n → Google Sheets |
| `FJLZaE4hG0JoFH6f` | Plane → Bot (prod) | ❌ УБРАТЬ | Заменить на прямой Plane webhook |
| `Y4fnJHlMGpABXCtq` | Plane → TG + Email | Нет | Уведомления о Plane событиях (отдельный TG) |
| `oebEvIxXE5yen48K` | ticket@hhivp.com → Plane | Нет | Email → Plane задача → Auto-reply |
| `avIhdXufIxxjjplg` | hhivp.com Contact Form | Нет | Контактная форма сайта |
| `t60PCfBbmkU9hp2Z` | Gomanic.ru | Нет | Другой проект |
| `HPVA6mjD0HPWMf71` | Gomanic.com.br | Нет | Другой проект |

### Интеграции бота с n8n

**1. Google Sheets Sync (НУЖЕН n8n)**
```
Bot создаёт TaskReport → POST n8n webhook → n8n записывает в Google Sheets
Причина: Google Sheets API требует OAuth, проще через n8n
```

**2. Plane Task Completed (УБРАТЬ n8n)**
```
БЫЛО:   Plane webhook → n8n → Bot
СТАНЕТ: Plane webhook → Bot напрямую (/webhooks/plane-direct)
Причина: n8n лишняя прослойка, добавляет баги
```

### Webhook Endpoints бота

| Endpoint | Источник | Описание |
|----------|----------|----------|
| `POST /webhooks/task-completed` | n8n (legacy) | Task reports от n8n |
| `POST /webhooks/plane-direct` | Plane (NEW) | Прямые webhooks от Plane |
| `POST /webhooks/ai/task-result` | n8n AI | Результат детекции задачи |
| `POST /webhooks/ai/voice-result` | n8n AI | Результат голосового отчёта |
| `GET /health` | Any | Health check |

### AI Integration (IMPLEMENTED ✅)

**Архитектура:** Бот = "thin client", вся AI логика в n8n

```
┌─────────────────┐     ┌────────────────────────────────────────┐
│  Telegram Bot   │     │                  n8n                   │
│                 │     │                                        │
│ Chat Monitor ───┼────►│  AI Task Detection                    │
│ (все сообщения) │     │  └─ OpenRouter (free Llama/Mistral)   │
│                 │     │  └─ Plane API                         │
│ Voice Handler ──┼────►│  AI Voice Report                      │
│ (голосовые)     │     │  └─ Whisper transcription             │
│                 │     │  └─ OpenRouter (extract data)         │
│ ◄───────────────┼─────┤  └─ Plane search + update             │
│ Callbacks       │     └────────────────────────────────────────┘
└─────────────────┘
```

**Файлы:**
- `app/services/n8n_ai_service.py` - отправка в n8n
- `app/handlers/ai_callbacks.py` - обработка кнопок
- `app/webhooks/server.py` - приём результатов
- `n8n-workflows/` - JSON для импорта в n8n

**n8n Workflows:**
- `ai-task-detection.json` - автодетекция задач в чатах
- `ai-voice-report.json` - обработка голосовых отчётов

**Настройка:**
```bash
# .env
N8N_URL=https://n8n.hhivp.com
N8N_WEBHOOK_SECRET=your_secret
AI_TASK_DETECTION_ENABLED=true
```

📚 Полная документация: `n8n-workflows/README.md`

---

## 🏗️ Architecture Overview

### Hybrid Structure

The project uses **two architectural approaches**:

```
app/
├── handlers/                # 🎯 Simple handlers (START HERE for new features)
│   ├── start.py            # /start, /help, /profile commands
│   ├── google_sheets_sync.py
│   └── new_feature.py      # 🆕 Add simple commands here
│
├── modules/                 # 🏗️ Complex modular features (advanced)
│   ├── task_reports/       # Client reporting automation (PRODUCTION)
│   ├── daily_tasks/        # Email → Plane.so (admin only)
│   ├── work_journal/       # Work entries with state management
│   └── common/             # Shared module utilities
│
├── services/                # 💼 Business logic
│   ├── task_reports_service.py
│   ├── work_journal_service.py
│   └── daily_tasks_service.py
│
├── database/                # 🗄️ SQLAlchemy models + Alembic
│   ├── models.py           # Core: BotUser
│   ├── task_reports_models.py
│   ├── work_journal_models.py
│   └── daily_tasks_models.py
│
├── middleware/              # 🔧 Request processing (rarely modify)
├── integrations/            # 🔗 External APIs (Plane, n8n)
└── utils/                   # 🛠️ Helpers and formatters
```

### When to Use What?

**Use `app/handlers/`** for:
- Simple commands (like `/ping`, `/echo`)
- Quick features without complex state
- Admin utilities
- **Recommended for new developers**

**Use `app/modules/`** for:
- Complex features with multiple handlers
- State-based workflows (FSM)
- Features requiring strict message isolation
- **Requires understanding of router priorities**

### Critical Router Loading Order

**MUST be maintained** in `app/main.py:244-264`:

```python
1. start.router              # Common commands (/start, /help)
2. daily_tasks_router        # Email processing (admin-only, FIRST priority)
3. task_reports_router       # Client reporting (state-based, NEW)
4. work_journal_router       # Work entries (state-based)
5. google_sheets_sync.router # Integration hooks
```

⚠️ **Order matters!** Daily Tasks email filter must be first to prevent conflicts.

### Module Isolation Strategy

**Each module MUST have filters** to prevent message conflicts.

#### Example: Daily Tasks (Email Processing)
```python
# app/modules/daily_tasks/filters.py
class IsAdminEmailFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        # Captures emails BEFORE other handlers
        return is_admin and is_email_format
```

Router order in `daily_tasks/router.py:18-25`:
1. `email_router` - Admin email → Plane tasks (FIRST!)
2. `navigation_router` + `callback_router` - UI interactions
3. `handlers_router` - Commands (/settings)

#### Example: Work Journal (State-based)
```python
# app/modules/work_journal/filters.py
class IsWorkJournalActiveFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        # Only process text during active work journal states
        return user_state in [DURATION, TRAVEL, COMPANY, ...]
```

Router order in `work_journal/router.py:18-24`:
1. `handlers_router` - Commands (/journal, /history)
2. `callback_router` - Button callbacks
3. `text_router` - Text input (LAST, state-filtered only)

### Middleware Stack

**Applied in strict order** (`app/main.py:165-181`):

| Order | Middleware | Purpose |
|-------|-----------|---------|
| 1 | DatabaseSessionMiddleware | Creates async DB session |
| 2 | PerformanceMiddleware | Request timing |
| 3 | LoggingMiddleware | Request/response logging |
| 4 | GroupMonitoringMiddleware | Group chat tracking |
| 5 | AuthMiddleware | User authorization |

All middleware applied to both `message` and `callback_query` handlers.

### Database Architecture

**Stack:** PostgreSQL + Redis, SQLAlchemy async + Alembic

**Key Models:**
- `models.py` - Core: `BotUser`, legacy work journal
- `task_reports_models.py` - `TaskReport` for client reports (NEW)
- `daily_tasks_models.py` - `AdminDailyTasksSettings`, `DailyTasksLog`
- `user_tasks_models.py` - `UserTasksCache` for Plane sync
- `work_journal_models.py` - Work journal v2 models

**Migrations:** `alembic/versions/` - Run with `alembic upgrade head`

### Key Services

**TaskReportsService** (`app/services/task_reports_service.py`)
- CRUD operations for TaskReport
- Auto-fill from Plane API (lines 254-459)
- Integration with work_journal and n8n

**DailyTasksService** (`app/services/daily_tasks_service.py`)
- Global singleton initialized in `main.py:46-48`
- Email parsing → Plane API task creation
- Scheduled notifications via `scheduler.py`

**WorkJournalService** (`app/services/work_journal_service.py`)
- CRUD for work entries
- Company/executor management
- n8n webhook integration for Google Sheets sync

**UserTasksCacheService** (`app/services/user_tasks_cache_service.py`)
- Caches Plane tasks per user
- Reduces API calls
- Auto-refresh mechanism

---

## 💡 Development Guide

### Adding New Simple Command

**File:** `app/handlers/new_feature.py`

```python
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from ..utils.logger import bot_logger

router = Router()

@router.message(Command("new_command"))
async def handle_new_command(message: Message):
    """Handler for new command"""
    bot_logger.info(f"New command called by user {message.from_user.id}")
    await message.reply("🆕 New feature works!")
```

**Register in** `app/main.py`:
```python
from .handlers import new_feature

async def main():
    # ...existing code...
    dp.include_router(new_feature.router)
    # ...rest of code...
```

### Adding New Module

1. **Create structure:**
```
app/modules/new_module/
├── __init__.py
├── router.py           # Main router
├── handlers.py         # Command handlers
├── filters.py          # Custom filters (CRITICAL for isolation)
├── keyboards.py        # Inline keyboards
├── states.py           # FSM states (if needed)
└── callback_handlers.py
```

2. **Implement filters** to prevent conflicts:
```python
class YourModuleFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        # Return True only for messages this module should handle
        return should_handle
```

3. **Add to main router** in `app/main.py` at correct priority position

4. **Test isolation**: Run `python3 test_modules_isolation.py`

### Working with Database

```python
from sqlalchemy import select
from ..database.database import async_session
from ..database.models import BotUser

@router.message(Command("mydata"))
async def get_user_data(message: Message):
    user_id = message.from_user.id

    async with async_session() as session:
        result = await session.execute(
            select(BotUser).where(BotUser.telegram_id == user_id)
        )
        user = result.scalar_one_or_none()

        if user:
            await message.reply(f"👤 Username: {user.username}")
        else:
            await message.reply("❌ User not found")
```

### Creating Database Model & Migration

**File:** `app/database/new_models.py`

```python
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from .database import Base

class NewFeature(Base):
    __tablename__ = 'new_features'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    data = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

**Create migration:**
```bash
docker exec -it telegram-bot-app alembic revision --autogenerate -m "Add new feature"
docker exec -it telegram-bot-app alembic upgrade head
```

### Useful Utilities

**Logging:**
```python
from ..utils.logger import bot_logger

bot_logger.info("Information")
bot_logger.warning("Warning")
bot_logger.error("Error")
```

**Admin Check:**
```python
from ..config import settings

if settings.is_admin(message.from_user.id):
    # Admin-only logic
    pass
```

**Formatters:**
```python
from ..utils.work_journal_formatters import format_duration
from ..utils.formatters import escape_markdown

# Time: 90 minutes → "1 hour 30 minutes"
formatted_time = format_duration(90)

# Safe markdown
safe_text = escape_markdown("Text with *special* characters")
```

---

## ⚙️ Configuration

**File:** `app/config.py` (Pydantic Settings)

### Required Environment Variables
```bash
TELEGRAM_TOKEN=bot_token_here
TELEGRAM_API_ID=12345
TELEGRAM_API_HASH=hash_here
ADMIN_USER_IDS=123456789,987654321    # Comma-separated
DATABASE_URL=postgresql+asyncpg://user:pass@host/db
REDIS_URL=redis://:pass@host:6379/0
```

### Optional (Plane.so)
```bash
PLANE_API_URL=https://plane.example.com
PLANE_API_TOKEN=token_here
PLANE_WORKSPACE_SLUG=workspace-slug
DAILY_TASKS_ENABLED=true
DAILY_TASKS_TIME=09:00                # HH:MM format
DAILY_TASKS_TIMEZONE=Europe/Moscow
```

### Optional (Integrations)
```bash
N8N_WEBHOOK_URL=https://n8n.example.com/webhook/...
N8N_WEBHOOK_SECRET=secret_here
GOOGLE_SHEETS_ID=spreadsheet_id_here
```

### Optional (Voice Transcription - FREE!)
```bash
# HuggingFace Whisper - FREE voice-to-text
HUGGINGFACE_API_KEY=hf_xxxxxxxxxxxxx

# OpenRouter - FREE AI models (Mistral, Llama)
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxx
```

Both APIs are FREE! No cost for voice transcription and AI extraction.

### Optional (AI Features - Enterprise v3.0)
```bash
OPENAI_API_KEY=sk-your-openai-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key
AI_MODEL=gpt-4-turbo
AI_TEMPERATURE=0.7
AI_MAX_TOKENS=2000
```

Without AI API keys, AI features are disabled (bot still works normally).

### Adding New Settings

**File:** `app/config.py`

```python
class Settings(BaseSettings):
    # ...existing settings...

    # New setting
    new_feature_enabled: bool = False
    new_api_token: Optional[str] = None

    class Config:
        env_file = ".env"
```

**In .env file:**
```env
NEW_FEATURE_ENABLED=true
NEW_API_TOKEN=your_token_here
```

---

## 🔐 Security & Credentials

### Important Files

**SECRETS.md** - Production credentials and API keys
- ⚠️ **NEVER commit to git** (in .gitignore)
- Contains: n8n API key, Plane tokens, bot tokens, etc.
- Use for local testing with production services

**.env** - Your local environment configuration
- ⚠️ **NEVER commit to git** (in .gitignore)
- Copy from `.env.example` and fill with real values
- See `SECRETS.md` for production credentials

**.env.example** - Template with placeholders
- ✅ Safe to commit to git
- Update when adding new configuration options

### Credentials Checklist

Before committing changes:
```bash
# Check that secrets are not staged
git status --porcelain | grep -E "SECRETS|\.env$"
# Should show nothing or "??" (untracked)

# Verify .gitignore is working
git check-ignore .env SECRETS.md
# Should show both files are ignored
```

### Production Services

**Production Server**:
- Host: `rd.hhivp.com`
- SSH: `ssh hhivp@rd.hhivp.com` (passwordless with RSA key)
- Bot path: `/opt/tg-modern-bot`
- Webhook port: **8083** (external) → 8080 (internal)
- SSH key: `~/.ssh/id_rsa` (4096-bit RSA, created 2025-10-22)

**n8n** (Automation & Google Sheets integration):
- URL: https://n8n.hhivp.com
- API Key: In `.env` as `N8N_API_KEY` (JWT token)
- API Docs: `https://n8n.hhivp.com/api/v1/docs`
- Sends webhooks to: `http://rd.hhivp.com:8083/webhooks/task-completed`
- API usage: `curl -H "X-N8N-API-KEY: $N8N_API_KEY" https://n8n.hhivp.com/api/v1/workflows`

**Plane.so** (Task Management):
- URL: https://plane.hhivp.com
- API token in `SECRETS.md`
- Projects: HHIVP, HARZL, DELTA, и др.

**Telegram Group**:
- Work Journal notifications: -1001682373643
- Plane notifications: -1001682373643 (Topic: 2231)

### Testing Production Integrations Locally

```bash
# 1. Copy credentials from SECRETS.md to .env manually

# 2. Start bot
make dev-restart

# 3. Test Work Journal → n8n → Google Sheets
# Send /work_journal to bot → fill entry → check Google Sheets

# 4. Test Daily Tasks → Plane.so
# Send email-formatted message as admin → check Plane.so + Telegram group

# 5. Test Task Reports → Client + Google Sheets
# Mark Plane task as Done → fill report → verify all integrations
```

---

## 🐛 Debugging

### Common Problems

**Bot not responding:**
```bash
make bot-logs  # Watch logs in real-time
```

**Database won't connect:**
```bash
make db-up     # Start DB separately
make db-shell  # Test connection
```

**Changes not applied:**

See [Quick Start > If Already Running](#if-already-running) for detailed workflow.

**TL;DR:**
- **Docker:** Must rebuild image + recreate container (NOT just restart!)
  ```bash
  make bot-rebuild-clean       # Recommended (Makefile)
  # Or manually:
  docker-compose build --no-cache telegram-bot
  docker-compose up -d --force-recreate telegram-bot
  ```

- **Local dev:** Code reloads automatically
  ```bash
  make dev-restart
  ```

⚠️ **Common mistakes:**
- `docker-compose restart` - only restarts OLD container ❌
- `docker-compose up -d` - doesn't recreate container ❌
- `docker-compose build` alone - doesn't update running container ❌

✅ **Must use:** `--force-recreate` flag or Makefile commands!

### Useful Log Commands
```bash
make bot-logs     # Bot logs (real-time)
make status       # Service status
tail -f logs/bot_output.log  # Direct log file
```

### Module-Specific Issues

**Email not being captured by daily_tasks:**
- Check `IsAdminEmailFilter` in `app/modules/daily_tasks/filters.py`
- Verify user is in `ADMIN_USER_IDS`
- Confirm `email_router` is first in `daily_tasks/router.py`

**Text captured by wrong module:**
- Check state filters in respective module `filters.py`
- Verify router loading order in `main.py`
- Test with `test_modules_isolation.py`

**Service initialization errors:**
- Check `on_startup()` function completes successfully in `main.py`
- Review `make bot-logs` for errors
- Verify required env variables are set

**Task Reports webhook not working:**
- Check webhook server is running: `make bot-status`
- Verify n8n workflow is active: https://n8n.hhivp.com/workflows
- Check logs: `make bot-logs | grep webhook`

### Bot Management

The bot uses `bot_manager.sh` script (called by Makefile):
- Manages single process via PID file
- Handles graceful restarts
- Logs to `logs/bot_output.log`

Production uses systemd service or Docker containers.

---

## 🧪 Testing Strategy

### Critical Tests (Run Before Committing)

**Module isolation is CRITICAL** - always test:
```bash
python3 test_modules_isolation.py  # Ensures filters work correctly
python3 test_email_fix.py          # Email handler isolation
```

### Integration Tests
```bash
python3 test_basic.py                      # Basic functionality
python3 test_daily_tasks_comprehensive.py  # Daily Tasks module
python3 test_plane_daily_tasks.py          # Plane.so integration
python3 test_task_reports_flow.py          # Task Reports end-to-end (NEW)
```

### Task Reports Test Script

Create realistic test task in Plane with description, comments & assignees:

```bash
# Set Plane API token (from SECRETS.md or .env)
export PLANE_API_TOKEN="plane_api_xxxx"

# Run the test script
./venv/bin/python /tmp/create_test_task.py
```

**What it creates:**
- ✅ Test task with full description (HTML format)
- ✅ 2 realistic comments in Russian
- ✅ Auto-assigned to your user (zarudesu@gmail.com)
- ✅ High priority

**Next steps after running:**
1. Mark task as "Done" in Plane UI
2. Check bot notification: `make bot-logs | grep "task-completed"`
3. Fill report as admin in Telegram
4. Verify all integrations (client + work_journal + Google Sheets + group)

**📖 Full Testing Guide:** [`docs/guides/task-reports-guide.md#-testing`](docs/guides/task-reports-guide.md#-testing)

### Manual Testing Checklist

- [ ] Email processing (Daily Tasks)
- [ ] Work Journal → Google Sheets
- [ ] Task Reports → Client + Google Sheets + Group
- [ ] Voice Transcription → AI extraction → Work Journal
- [ ] Router isolation (no message conflicts)
- [ ] Admin-only features (verify permissions)

---

## 📚 References

### Documentation
- [`docs/guides/task-reports-guide.md`](docs/guides/task-reports-guide.md) - Task Reports complete guide
- [`docs/TASK_REPORTS_FLOW.md`](docs/TASK_REPORTS_FLOW.md) - Flow diagrams
- [`TASK_REPORTS_FIXES.md`](TASK_REPORTS_FIXES.md) - Bug fixes history
- [`docs/README.md`](docs/README.md) - Documentation index

### Architecture
- `app/main.py:244-264` - Router loading order (CRITICAL)
- `app/main.py:165-181` - Middleware stack
- `app/config.py` - Configuration & settings

### Key Files
- `app/webhooks/server.py` - Webhook endpoints (Task Reports, n8n)
- `app/services/task_reports_service.py:254-459` - Task Reports autofill logic
- `app/modules/task_reports/handlers/approval.py` - approve_send with full integration
- `bot_manager.sh` - Bot process management

---

## 🚧 Enterprise Architecture (v3.0) - BETA

**Status:** In development, not production ready

### Core Systems

**Event Bus** (`app/core/events/`):
- Reactive event-driven architecture
- Priority-based event handling
- 7+ event types: MessageReceived, TaskCreated, AIRequest, etc.

**Plugin System** (`app/core/plugins/`):
- Dynamic plugin loading/unloading
- Dependency management between plugins

**AI Abstractions** (`app/core/ai/`):
- Universal LLM provider interface
- OpenAI and Anthropic Claude support
- Conversation history and cost tracking

### Enterprise Modules

**AI Assistant** (`app/modules/ai_assistant/`):
- `/ai <question>` - Chat with AI
- `/ai_summary` - Summarize chat context
- `/ai_auto_task` - Auto-detect tasks from messages

**Chat Monitor** (`app/modules/chat_monitor/`):
- Reads all group messages
- Maintains context (last 50 messages per chat)
- `/monitor_start`, `/monitor_stop`, `/monitor_status`

---

## 📝 Documentation Maintenance

### When to Update This File

1. **After fixing critical issues** — Update Known Issues section
2. **After adding new features** — Update Module Status Dashboard
3. **After changing architecture** — Update Architecture Overview
4. **After adding n8n workflows** — Update n8n Integration Plans

### Related Documentation

| File | Purpose | Update When |
|------|---------|-------------|
| `docs/ROADMAP.md` | Technical debt & roadmap | After completing issues |
| `docs/guides/task-reports-guide.md` | Task Reports module | After module changes |
| `docs/guides/support-requests-guide.md` | Support module | After module changes |
| `docs/guides/ai-integration-guide.md` | AI через n8n (Task Detection, Voice) | After AI changes |
| `n8n-workflows/README.md` | n8n workflows setup | After n8n changes |
| `SECRETS.md` | Production credentials | After credential changes |

---

**Last Updated:** 2026-01-25
**Bot Version:** 3.0 (Chat AI Analysis: Persistent Context + Problem Detection + Summarization)
**Current Phase:** Phase 1 - Critical Fixes
**Questions?** Check logs: `make bot-logs` or `./deploy.sh logs`

📚 **See also:**
- [docs/ROADMAP.md](docs/ROADMAP.md) - Development roadmap & technical debt
- [docs/guides/ai-integration-guide.md](docs/guides/ai-integration-guide.md) - AI Integration (n8n + OpenRouter)
- [n8n-workflows/README.md](n8n-workflows/README.md) - n8n Workflows setup
- [README_DOCKER.md](README_DOCKER.md) - Docker development guide
