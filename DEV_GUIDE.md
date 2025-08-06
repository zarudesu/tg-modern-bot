# ⚡ DEVELOPER GUIDE - Modern Telegram Bot

> **Optimized instructions for rapid feature development**

---

## ⚡ QUICK START (30 seconds)

### If project NOT running:
```bash
cd /path/to/tg-mordern-bot

# If .env doesn't exist
cp .env.example .env
# Add your token: TELEGRAM_TOKEN=your_token

# Start (database in Docker, bot locally)  
make dev
```

### If project already running:
```bash
cd /path/to/tg-mordern-bot
make dev-restart  # Quick restart
```

---

## 🏗️ PROJECT ARCHITECTURE

### 📁 **Development structure:**
```
app/
├── handlers/           # 🎯 Telegram handlers (add new commands here)
│   ├── start.py       # Basic commands (/start, /help)  
│   ├── work_journal.py # ✅ Work journal (ready)
│   └── new_feature.py # 🆕 Add new features here
├── services/          # 💼 Business logic
│   ├── work_journal_service.py # ✅ Ready journal service
│   └── new_service.py # 🆕 New services
├── database/          # 🗄️ DB models
│   ├── models.py      # Main models
│   ├── work_journal_models.py # ✅ Ready journal models
│   └── database.py    # DB connection
├── middleware/        # 🔧 Middleware (rarely modified)
├── utils/            # 🛠️ Utilities and helpers
└── integrations/     # 🔗 External APIs
```

### 🎯 **Where to add what:**
- **New bot commands** → `app/handlers/new_feature.py`
- **Business logic** → `app/services/new_service.py`  
- **DB models** → `app/database/new_models.py`
- **Utilities** → `app/utils/new_helper.py`

---

## 🛠️ DEVELOPMENT COMMANDS

### **Main commands:**
```bash
make dev          # 🚀 Start development (recommended)
make dev-restart  # ⚡ Quick restart  
make dev-stop     # 🛑 Stop development

make db-up        # 🗄️ Database only
make db-shell     # 💻 PostgreSQL console
make db-admin     # 🌐 pgAdmin (localhost:8080)

make bot-logs     # 📝 Bot logs in real time
make status       # 📊 All services status
```

### **Testing:**
```bash
# Quick tests
python test_basic.py          # Basic connections
python test_work_journal.py   # Work journal

# All tests
make test
```

---

## 🆕 CREATING NEW FEATURE

### **1. Create handler:**
```python
# app/handlers/new_feature.py
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

### **2. Connect in main.py:**
```python
# app/main.py (add import and registration)
from .handlers import new_feature

async def main():
    # ...existing code...
    dp.include_router(new_feature.router)
    # ...rest of code...
```

### **3. If DB needed - create model:**
```python
# app/database/new_models.py
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

---

## 💡 READY EXAMPLES

### **Simple command:**
```python
@router.message(Command("ping"))  
async def ping_command(message: Message):
    await message.reply("🏓 Pong!")
```

### **Inline keyboard:**
```python
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

@router.message(Command("menu"))
async def show_menu(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 Option 1", callback_data="opt1")],
        [InlineKeyboardButton(text="⚡ Option 2", callback_data="opt2")]
    ])
    await message.reply("Choose option:", reply_markup=keyboard)

@router.callback_query(F.data == "opt1")
async def handle_option1(callback: CallbackQuery):
    await callback.message.edit_text("✅ Option 1 selected!")
```

### **Database work:**
```python
from sqlalchemy import select
from ..database.database import async_session
from ..database.work_journal_models import WorkJournalEntry

async def get_entries_for_user(user_id: int):
    """Get user entries"""
    async with async_session() as session:
        result = await session.execute(
            select(WorkJournalEntry).where(WorkJournalEntry.telegram_user_id == user_id)
        )
        return result.scalars().all()
```

---

## 🔧 USEFUL UTILITIES

### **Logging:**
```python
from ..utils.logger import bot_logger

bot_logger.info("Information")
bot_logger.warning("Warning")
bot_logger.error("Error")
```

### **Database connection:**
```python
from ..database.database import async_session

async def work_with_db():
    async with async_session() as session:
        # Your DB work
        pass
```

---

## ⚙️ CONFIGURATION

### **Add new settings:**
```python
# app/config.py
class Settings(BaseSettings):
    # ...existing settings...
    
    # New setting
    new_feature_enabled: bool = False
    new_api_token: Optional[str] = None
    
    class Config:
        env_file = ".env"
```

### **In .env file:**
```env
NEW_FEATURE_ENABLED=true
NEW_API_TOKEN=your_token_here
```

---

## 🚨 DEBUGGING

### **Common issues:**

#### **Bot not responding:**
```bash
make bot-logs  # Watch logs in real time
```

#### **DB not connecting:**
```bash  
make db-up     # Start DB separately
make db-shell  # Check connection
```

#### **Changes not applying:**
```bash
make dev-restart  # Restart with new code
```

---

## 🚀 DEPLOYMENT

### **Local development:**
```bash
make dev-restart  # Restart with changes
```

### **Testing before commit:**
```bash
python test_basic.py          # Basic tests
python test_work_journal.py   # Module testing
make test                     # All tests
```

### **Commit changes:**
```bash
git add .
git commit -m "🆕 Add new feature: description"  
git push origin main
```

---

*📅 Updated: August 2025*  
*🚀 Ready for rapid development!*
