# ⚡ CLAUDE QUICK REFERENCE - TG Bot

> **Максимально сжатая шпаргалка для мгновенного старта**

---

## 🏁 INSTANT START
```bash
cd /Users/zardes/Projects/tg-mordern-bot
make dev-restart  # Если уже запущен
# ИЛИ
make dev         # Если не запущен
```

---

## 📁 СТРУКТУРА (куда добавлять код)
```
app/
├── handlers/          # 🎯 НОВЫЕ КОМАНДЫ БОТА
├── services/          # 💼 БИЗНЕС-ЛОГИКА  
├── database/          # 🗄️ МОДЕЛИ БД
├── utils/            # 🛠️ УТИЛИТЫ
└── integrations/     # 🔗 ВНЕШНИЕ API
```

---

## 🆕 НОВАЯ КОМАНДА (2 шага)
### 1. Создать обработчик:
```python
# app/handlers/my_feature.py
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()

@router.message(Command("test"))
async def test_cmd(message: Message):
    await message.reply("✅ Работает!")
```

### 2. Подключить в main.py:
```python
# app/main.py (добавить)
from .handlers import my_feature
dp.include_router(my_feature.router)
```

---

## 🔧 КОМАНДЫ
```bash
make dev-restart    # ⚡ Перезапуск
make bot-logs       # 📝 Логи
make db-shell       # 💻 БД консоль
make status         # 📊 Статус сервисов
python test_basic.py # 🧪 Тест
```

---

## 🗄️ РАБОТА С БД
```python
from ..database.database import async_session
from sqlalchemy import select

async with async_session() as session:
    result = await session.execute(select(Model))
    items = result.scalars().all()
```

---

## 🎹 КЛАВИАТУРЫ  
```python
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅ OK", callback_data="ok")]
])
await message.reply("Текст", reply_markup=keyboard)
```

---

## 📝 ЛОГИРОВАНИЕ
```python  
from ..utils.logger import bot_logger
bot_logger.info("Сообщение")
```

---

## 🚨 ЕСЛИ НЕ РАБОТАЕТ
```bash
make dev-restart  # Перезапуск
make bot-logs     # Смотреть ошибки
make db-up        # БД отдельно если нужно
```

---

## 📂 ГОТОВЫЕ ПРИМЕРЫ В ПРОЕКТЕ
- `app/handlers/start.py` - базовые команды
- `app/handlers/work_journal.py` - сложная логика
- `app/services/work_journal_service.py` - сервис с БД
- `app/database/work_journal_models.py` - модели БД

---

**🎯 ВСЕ! Теперь можем быстро разрабатывать!**
