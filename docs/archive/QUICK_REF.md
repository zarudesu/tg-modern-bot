# ⚡ QUICK REFERENCE - TG Bot

> **Ultra-compressed cheat sheet for instant start**

---

## 🏁 INSTANT START
```bash
cd /path/to/tg-mordern-bot
make dev-restart  # If already running
# OR
make dev         # If not running
```

---

## 📁 STRUCTURE (where to add code)
```
app/
├── handlers/          # 🎯 NEW BOT COMMANDS
├── services/          # 💼 BUSINESS LOGIC  
├── database/          # 🗄️ DB MODELS
├── utils/            # 🛠️ UTILITIES
└── integrations/     # 🔗 EXTERNAL APIs
```

---

## 🆕 NEW COMMAND (2 steps)
### 1. Create handler:
```python
# app/handlers/my_feature.py
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()

@router.message(Command("test"))
async def test_cmd(message: Message):
    await message.reply("✅ Works!")
```

### 2. Connect in main.py:
```python
# app/main.py (add)
from .handlers import my_feature
dp.include_router(my_feature.router)
```

---

## 🔧 COMMANDS
```bash
make dev-restart    # ⚡ Restart
make bot-logs       # 📝 Logs
make db-shell       # 💻 DB console
make status         # 📊 Services status
python test_basic.py # 🧪 Test
```

---

## 🗄️ DATABASE WORK
```python
from ..database.database import async_session
from sqlalchemy import select

async with async_session() as session:
    result = await session.execute(select(Model))
    items = result.scalars().all()
```

---

## 🎹 KEYBOARDS  
```python
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅ OK", callback_data="ok")]
])
await message.reply("Text", reply_markup=keyboard)
```

---

## 📝 LOGGING
```python  
from ..utils.logger import bot_logger
bot_logger.info("Message")
```

---

## 🚨 IF NOT WORKING
```bash
make dev-restart  # Restart
make bot-logs     # Check errors
make db-up        # DB separately if needed
```

---

## 📂 READY EXAMPLES IN PROJECT
- `app/handlers/start.py` - basic commands
- `app/handlers/work_journal.py` - complex logic
- `app/services/work_journal_service.py` - service with DB
- `app/database/work_journal_models.py` - DB models

---

**🎯 DONE! Now we can develop quickly!**
