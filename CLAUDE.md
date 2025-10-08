# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🚧 ACTIVE REFACTORING: Task Reports Module

**Status:** Planning complete, ready to start
**Branch:** `refactor/task-reports-module` (to be created)
**Documentation:**
- `docs/TASK_REPORTS_REFACTORING.md` - Полный план рефакторинга
- `docs/CURRENT_BUGS.md` - Детальное описание 5 багов

**Before making ANY changes to task_reports module, read these files first!**

## Essential Commands

### Development Workflow
```bash
# Quick start
make dev                          # Start database + bot
make dev-restart                  # Restart bot only
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
python3 test_modules_isolation.py # Module isolation (CRITICAL)
python3 test_email_fix.py         # Email filter tests

# Integration testing (локально с продакшн сервисами)
# 1. Work Journal → n8n → Google Sheets
# 2. Daily Tasks → Plane.so notifications
# 3. Group notifications
# См. SECRETS.md для credentials
```

### Production
```bash
make prod-deploy                  # Full deployment
make prod-up                      # Start services
make prod-logs                    # View logs
make prod-backup                  # Backup database
```

## Architecture Overview

### Hybrid Structure
The project uses **two architectural approaches**:

```
app/
├── handlers/                # 🎯 Simple handlers (ADD NEW FEATURES HERE)
│   ├── start.py            # /start, /help, /profile commands
│   ├── google_sheets_sync.py
│   └── new_feature.py      # 🆕 Add new simple commands here
│
├── modules/                 # 🏗️ Complex modular features (advanced)
│   ├── daily_tasks/        # Email → Plane.so (admin only, highest priority)
│   ├── work_journal/       # Work entries with state management
│   └── common/             # Shared module utilities
│
├── services/                # 💼 Business logic
│   ├── work_journal_service.py
│   ├── daily_tasks_service.py
│   └── new_service.py      # 🆕 Add business logic here
│
├── database/                # 🗄️ SQLAlchemy models + Alembic
│   ├── models.py           # Core models (User, etc)
│   ├── work_journal_models.py
│   ├── daily_tasks_models.py
│   ├── database.py         # DB connection
│   └── new_models.py       # 🆕 Add new models here
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
**MUST be maintained** in `app/main.py:186-202`:

```python
1. start.router              # Common commands (/start, /help)
2. daily_tasks_router        # Email processing (admin-only)
3. work_journal_router       # Work entries (state-based)
4. google_sheets_sync.router # Integration hooks
```

### Module Isolation Strategy

#### Daily Tasks (`app/modules/daily_tasks/`)
**Email processing with highest priority**

Router order in `router.py:18-25`:
1. `email_router` - Admin email → Plane tasks (FIRST)
2. `navigation_router` + `callback_router` - UI interactions
3. `handlers_router` - Commands (/settings)

Key isolation: `IsAdminEmailFilter` in `filters.py` ensures emails are captured before other handlers

#### Work Journal (`app/modules/work_journal/`)
**State-managed text processing**

Router order in `router.py:18-24`:
1. `handlers_router` - Commands (/journal, /history)
2. `callback_router` - Button callbacks
3. `text_router` - Text input (LAST, state-filtered only)

Key isolation: `IsWorkJournalActiveFilter` in `filters.py` ensures text only processed during active work journal states

### Middleware Stack
**Applied in strict order** (`app/main.py:165-181`):

```python
1. DatabaseSessionMiddleware  # Creates async DB session (FIRST)
2. PerformanceMiddleware      # Request timing
3. LoggingMiddleware          # Request/response logging
4. GroupMonitoringMiddleware  # Group chat tracking
5. AuthMiddleware             # User authorization (LAST)
```

All middleware applied to both `message` and `callback_query` handlers.

### Database Architecture

**Stack**: PostgreSQL + Redis, SQLAlchemy async + Alembic

Key models:
- `app/database/models.py` - Core: `BotUser`, legacy work journal
- `app/database/daily_tasks_models.py` - `AdminDailyTasksSettings`, `DailyTasksLog`
- `app/database/user_tasks_models.py` - `UserTasksCache` for Plane sync
- `app/database/work_journal_models.py` - Work journal v2 models
- `app/database/task_reports_models.py` - `TaskReport` for client reports (NEW)

Migrations: `alembic/versions/` - Run with `alembic upgrade head`

### Task Reports System (NEW)

**Purpose**: Automated client reporting when support requests are completed in Plane.so

When a task is marked as "Done" in Plane:
1. n8n webhook detects status change → sends to bot
2. Bot creates TaskReport (pending status)
3. Admin who closed task gets reminder to fill report
4. Admin fills report (autofilled from work_journal if available)
5. Report sent to client in original chat

**Key files**:
- `app/database/task_reports_models.py` - TaskReport model
- `alembic/versions/004_add_task_reports.py` - Database migration
- `docs/TASK_REPORTS_PLAN.md` - Complete implementation plan (400+ lines)

**Status flow**: `pending → draft → approved → sent_to_client`

**Reminder system**: Escalating notifications (1hr → 3hr → 6hr) until report filled

**Integration points**:
- n8n workflow: "hook from plane to tg + email reply" (ID: Y4fnJHlMGpABXCtq)
- Plane webhook: Tracks `actor` field (who closed task)
- Work journal: Auto-fill from recent entries
- Support requests: Links via `support_request_id` foreign key

**Development status**:
- ✅ Database models created
- ✅ Migration ready
- ✅ Architecture documented
- ⏳ Service layer pending
- ⏳ FSM handlers pending
- ⏳ n8n workflow update pending

See `docs/TASK_REPORTS_PLAN.md` for complete implementation details.

### Configuration

**File**: `app/config.py` (Pydantic Settings)

Required environment variables:
```bash
TELEGRAM_TOKEN=bot_token_here
TELEGRAM_API_ID=12345
TELEGRAM_API_HASH=hash_here
ADMIN_USER_IDS=123456789,987654321    # Comma-separated
DATABASE_URL=postgresql+asyncpg://user:pass@host/db
REDIS_URL=redis://:pass@host:6379/0
```

Optional (Plane.so):
```bash
PLANE_API_URL=https://plane.example.com
PLANE_API_TOKEN=token_here
PLANE_WORKSPACE_SLUG=workspace-slug
DAILY_TASKS_ENABLED=true
DAILY_TASKS_TIME=09:00                # HH:MM format
DAILY_TASKS_TIMEZONE=Europe/Moscow
```

Optional (integrations):
```bash
N8N_WEBHOOK_URL=https://n8n.example.com/webhook/...
N8N_WEBHOOK_SECRET=secret_here
GOOGLE_SHEETS_ID=spreadsheet_id_here
```

### Key Services

**Daily Tasks Service** (`app/services/daily_tasks_service.py`)
- Global singleton initialized in `main.py:46-48`
- Email parsing → Plane API task creation
- Scheduled notifications via `scheduler.py`
- Admin-only access

**Work Journal Service** (`app/services/work_journal_service.py`)
- CRUD for work entries
- Company/executor management
- n8n webhook integration for Google Sheets sync

**User Tasks Cache Service** (`app/services/user_tasks_cache_service.py`)
- Caches Plane tasks per user
- Reduces API calls
- Auto-refresh mechanism

### Adding New Modules

1. **Create structure**:
```
app/modules/new_module/
├── __init__.py
├── router.py           # Main router
├── handlers.py         # Command handlers
├── filters.py          # Custom filters (CRITICAL for isolation)
└── callback_handlers.py
```

2. **Implement filters** to prevent conflicts:
```python
class YourModuleFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        # Return True only for messages this module should handle
        # Consider: command patterns, user states, message types
        return should_handle
```

3. **Add to main router** in `app/main.py` at correct priority position

4. **Test isolation**: Run `python3 test_modules_isolation.py`

### Testing Strategy

**Module isolation is CRITICAL** - always test:
```bash
python3 test_modules_isolation.py  # Ensures filters work correctly
python3 test_email_fix.py          # Email handler isolation
```

Integration tests:
```bash
python3 test_daily_tasks_comprehensive.py
python3 test_plane_daily_tasks.py
```

### Common Issues

**Email not being captured by daily_tasks**:
- Check `IsAdminEmailFilter` in `app/modules/daily_tasks/filters.py`
- Verify user is in `ADMIN_USER_IDS`
- Confirm `email_router` is first in `daily_tasks/router.py`

**Text captured by wrong module**:
- Check state filters in `work_journal/filters.py`
- Verify router loading order in `main.py`
- Test with `test_modules_isolation.py`

**Service initialization errors**:
- `daily_tasks_service` must be initialized in `main.py` startup
- Check `on_startup()` function completes successfully
- Review `make bot-logs` for errors

### Bot Management

The bot uses `bot_manager.sh` script (called by Makefile):
- Manages single process via PID file
- Handles graceful restarts
- Logs to `logs/bot_output.log`

Production uses systemd service or Docker containers.

---

## Quick Start Guide

### First Time Setup
```bash
cd /Users/zardes/Projects/tg-mordern-bot

# If .env doesn't exist
cp .env.example .env
# Add your token: TELEGRAM_TOKEN=your_token

# Start (database in Docker, bot locally)
make dev
```

### If Already Running
```bash
cd /Users/zardes/Projects/tg-mordern-bot
make dev-restart  # Fast restart
```

---

## Creating New Features

### 1. Simple Command Handler

**File**: `app/handlers/new_feature.py`

```python
from aiogram import Router, F
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

### 2. Command with Inline Keyboard

```python
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

@router.message(Command("menu"))
async def show_menu(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 Option 1", callback_data="opt1")],
        [InlineKeyboardButton(text="⚡ Option 2", callback_data="opt2")]
    ])
    await message.reply("Choose an option:", reply_markup=keyboard)

@router.callback_query(F.data == "opt1")
async def handle_option1(callback: CallbackQuery):
    await callback.message.edit_text("✅ Option 1 selected!")
    await callback.answer()
```

### 3. Working with Database

```python
from sqlalchemy import select
from ..database.database import async_session
from ..database.models import User

@router.message(Command("mydata"))
async def get_user_data(message: Message):
    user_id = message.from_user.id

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        user = result.scalar_one_or_none()

        if user:
            await message.reply(f"👤 Username: {user.username}")
        else:
            await message.reply("❌ User not found")
```

### 4. Creating New Database Model

**File**: `app/database/new_models.py`

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

**Create migration**:
```bash
# Inside Docker container
docker exec -it telegram-bot-app alembic revision --autogenerate -m "Add new feature"
docker exec -it telegram-bot-app alembic upgrade head
```

---

## Useful Utilities

### Logging
```python
from ..utils.logger import bot_logger

bot_logger.info("Information")
bot_logger.warning("Warning")
bot_logger.error("Error")
```

### Admin Check
```python
from ..config import settings

if settings.is_admin(message.from_user.id):
    # Admin-only logic
    pass
```

### Formatters (Ready-to-use)
```python
from ..utils.work_journal_formatters import format_duration
from ..utils.formatters import escape_markdown

# Time: 90 minutes → "1 hour 30 minutes"
formatted_time = format_duration(90)

# Safe markdown
safe_text = escape_markdown("Text with *special* characters")
```

---

## Database Quick Reference

### Connection Pattern
```python
from ..database.database import async_session

async def work_with_db():
    async with async_session() as session:
        # Your DB work here
        await session.commit()
```

### Existing Models
- `User` (or `BotUser`) - Bot users
- `WorkJournalEntry` - Work journal entries
- `WorkJournalWorker` - Workers
- `WorkJournalCompany` - Companies
- `AdminDailyTasksSettings` - Daily tasks config
- `UserTasksCache` - Cached Plane tasks

### Database Commands
```bash
make db-shell     # Connect to PostgreSQL
make db-backup    # Create backup
make db-up        # Start database only
```

---

## Debugging

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
```bash
make dev-restart  # Restart with new code
```

### Useful Log Commands
```bash
make bot-logs     # Bot logs
make status       # Service status
tail -f logs/bot_output.log  # Direct log file
```

---

## Testing Your Feature

**Create test file**: `test_new_feature.py`

```python
import asyncio
from app.handlers.new_feature import handle_new_command

async def test_new_feature():
    """Test new feature"""
    print("🧪 Testing new feature...")
    # Your tests
    print("✅ Feature working!")

if __name__ == "__main__":
    asyncio.run(test_new_feature())
```

**Run**:
```bash
python3 test_new_feature.py
```

---

## Configuration

### Adding New Settings

**File**: `app/config.py`

```python
class Settings(BaseSettings):
    # ...existing settings...

    # New setting
    new_feature_enabled: bool = False
    new_api_token: Optional[str] = None

    class Config:
        env_file = ".env"
```

**In .env file**:
```env
NEW_FEATURE_ENABLED=true
NEW_API_TOKEN=your_token_here
```

**Usage**:
```python
from ..config import settings

if settings.new_feature_enabled:
    # feature logic
    pass
```

---

## 🔐 Security & Credentials

### Important Files

**SECRETS.md** - Contains all production credentials and API keys
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
# 1. Copy credentials from SECRETS.md to .env
cp SECRETS.md .env  # Don't do this literally, copy values manually

# 2. Start bot
make dev-restart

# 3. Test Work Journal → n8n → Google Sheets
# Send /work_journal to @zardes_bot
# Fill entry and submit
# Check Google Sheets for new row

# 4. Test Daily Tasks → Plane.so
# Send email-formatted message as admin
# Check Plane.so for new task
# Check Telegram group for notification
```

---

## Enterprise Architecture (v3.0)

### Core Systems

**Event Bus** (`app/core/events/`):
- Reactive event-driven architecture
- Priority-based event handling
- Middleware support for event processing
- 7+ event types: MessageReceived, TaskCreated, AIRequest, etc.

**Plugin System** (`app/core/plugins/`):
- Dynamic plugin loading/unloading
- Dependency management between plugins
- Base types: MessagePlugin, CallbackPlugin, AIPlugin

**AI Abstractions** (`app/core/ai/`):
- Universal LLM provider interface
- OpenAI and Anthropic Claude support
- Conversation history and cost tracking
- Configurable temperature, max_tokens, etc.

### Enterprise Modules

**AI Assistant** (`app/modules/ai_assistant/`):
- `/ai <question>` - Chat with AI
- `/ai_summary` - Summarize chat context
- `/ai_auto_task` - Auto-detect tasks from messages
- `/ai_help` - AI features help

**Chat Monitor** (`app/modules/chat_monitor/`):
- Reads all group messages
- Maintains context (last 50 messages per chat)
- `/monitor_start`, `/monitor_stop`, `/monitor_status`

### AI Configuration

Add to `.env`:
```env
OPENAI_API_KEY=sk-your-openai-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key
AI_MODEL=gpt-4-turbo
AI_TEMPERATURE=0.7
AI_MAX_TOKENS=2000
```

Without API keys, AI features are disabled (bot still works normally)
```