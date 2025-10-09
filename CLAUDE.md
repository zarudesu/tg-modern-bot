# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## 📑 Table of Contents

- [Quick Start](#-quick-start)
- [Essential Commands](#-essential-commands)
- [Module Status Dashboard](#-module-status-dashboard)
- [Architecture Overview](#-architecture-overview)
- [Development Guide](#-development-guide)
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

**Local dev (bot_manager.sh):**
```bash
make dev-restart  # Fast restart
make bot-logs     # View logs
```

**Docker deployment:**
```bash
# Apply code changes (FULL REBUILD without cache!)
docker-compose build --no-cache telegram-bot
docker-compose up -d --force-recreate telegram-bot

# Or single command (for specific service):
docker-compose up -d --build --force-recreate --no-deps telegram-bot

# View logs
docker logs telegram-bot-app-full -f
```

---

## ⚡ Essential Commands

### Development Workflow
```bash
# Core commands
make dev                          # Start database + bot
make dev-restart                  # Restart bot only (FAST)
make dev-stop                     # Stop everything

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

### Production
```bash
make prod-deploy                  # Full deployment
make prod-up                      # Start services
make prod-logs                    # View logs
make prod-backup                  # Backup database
```

---

## 📊 Module Status Dashboard

| Module | Status | Location | Documentation |
|--------|--------|----------|---------------|
| **Task Reports** | ✅ PRODUCTION | `app/modules/task_reports/` | [`docs/guides/task-reports-guide.md`](docs/guides/task-reports-guide.md) |
| **Daily Tasks** | ✅ PRODUCTION | `app/modules/daily_tasks/` | Email → Plane.so automation |
| **Work Journal** | ✅ PRODUCTION | `app/modules/work_journal/` | Work entries → Google Sheets |
| **AI Assistant** | 🚧 BETA | `app/modules/ai_assistant/` | OpenAI/Anthropic integration |
| **Chat Monitor** | 🚧 BETA | `app/modules/chat_monitor/` | Context tracking |

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

**Recent Fixes:**
- BUG #5 (2025-10-08): `approve_send` now creates work_journal + Google Sheets sync

**📚 Full Documentation:** [`docs/guides/task-reports-guide.md`](docs/guides/task-reports-guide.md)

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

**n8n** (Automation & Google Sheets integration):
- URL: https://n8n.hhivp.com
- Credentials in `SECRETS.md`

**Plane.so** (Task Management):
- URL: https://plane.hhivp.com
- API token in `SECRETS.md`

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

Depends on your setup:

```bash
# If running in Docker (production/staging):
# Step 1: Rebuild WITHOUT cache (important!)
docker-compose build --no-cache telegram-bot

# Step 2: Force recreate container
docker-compose up -d --force-recreate telegram-bot

# Alternative: single command (rebuilds but may use cache for some layers)
docker-compose up -d --build --force-recreate --no-deps telegram-bot

# If running locally (dev):
make dev-restart  # Restart bot process only
```

⚠️ **Important:**
- `make dev-restart` does NOT rebuild Docker images!
- `docker-compose build` without `--no-cache` may use cached layers and NOT apply code changes
- Always use `--no-cache` flag when rebuilding after code changes

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

**Last Updated:** 2025-10-08
**Bot Version:** 2.5 (Task Reports Production Ready)
**Questions?** Check logs: `make bot-logs`
