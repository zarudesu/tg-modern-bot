# Development Guide

> Extracted from CLAUDE.md. Code examples for common development tasks.

## Adding New Simple Command

**File:** `app/handlers/new_feature.py`

```python
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from ..utils.logger import bot_logger

router = Router()

@router.message(Command("new_command"))
async def handle_new_command(message: Message):
    bot_logger.info(f"New command called by user {message.from_user.id}")
    await message.reply("New feature works!")
```

**Register in** `app/main.py`:
```python
from .handlers import new_feature
dp.include_router(new_feature.router)
```

## Adding New Module

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
        return should_handle
```

3. **Add to main router** in `app/main.py` at correct priority position

4. **Test isolation**: Run `python3 test_modules_isolation.py`

## Working with Database

```python
from sqlalchemy import select
from ..database.database import async_session
from ..database.models import BotUser

@router.message(Command("mydata"))
async def get_user_data(message: Message):
    async with async_session() as session:
        result = await session.execute(
            select(BotUser).where(BotUser.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
```

## Creating Database Model & Migration

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

```bash
docker exec -it telegram-bot-app alembic revision --autogenerate -m "Add new feature"
docker exec -it telegram-bot-app alembic upgrade head
```

## Useful Utilities

```python
from ..utils.logger import bot_logger
from ..config import settings
from ..utils.work_journal_formatters import format_duration
from ..utils.formatters import escape_markdown

bot_logger.info("Information")
settings.is_admin(message.from_user.id)
format_duration(90)  # → "1 hour 30 minutes"
escape_markdown("Text with *special* characters")
```

## Configuration (app/config.py)

### Required Environment Variables
```bash
TELEGRAM_TOKEN=bot_token_here
TELEGRAM_API_ID=12345
TELEGRAM_API_HASH=hash_here
ADMIN_USER_IDS=123456789,987654321
DATABASE_URL=postgresql+asyncpg://user:pass@host/db
REDIS_URL=redis://:pass@host:6379/0
```

### Optional (Plane.so)
```bash
PLANE_API_URL=https://plane.example.com
PLANE_API_TOKEN=token_here
PLANE_WORKSPACE_SLUG=workspace-slug
DAILY_TASKS_ENABLED=true
DAILY_TASKS_TIME=09:00
DAILY_TASKS_TIMEZONE=Europe/Moscow
```

### Optional (Integrations)
```bash
N8N_WEBHOOK_URL=https://n8n.example.com/webhook/...
N8N_WEBHOOK_SECRET=secret_here
GOOGLE_SHEETS_ID=spreadsheet_id_here
HUGGINGFACE_API_KEY=hf_xxxxxxxxxxxxx    # FREE voice-to-text
OPENROUTER_API_KEY=sk-or-v1-xxxxx       # FREE AI models
```

### Adding New Settings

**File:** `app/config.py`
```python
class Settings(BaseSettings):
    new_feature_enabled: bool = False
    new_api_token: Optional[str] = None
```
