# 🚀 CLAUDE DEV GUIDE - Modern Telegram Bot

> **Оптимизированные инструкции для быстрой разработки новых фич с Claude**

---

## ⚡ БЫСТРЫЙ СТАРТ (30 секунд)

### Если проект НЕ запущен:
```bash
cd /Users/zardes/Projects/tg-mordern-bot

# Если .env НЕ существует
cp .env.example .env
# Добавить токен: TELEGRAM_TOKEN=ваш_токен

# Запуск (база в Docker, бот локально)  
make dev
```

### Если проект уже работает:
```bash
cd /Users/zardes/Projects/tg-mordern-bot
make dev-restart  # Быстрый перезапуск
```

---

## 🏗️ АРХИТЕКТУРА ПРОЕКТА

### 📁 **Структура для разработки:**
```
app/
├── handlers/           # 🎯 Telegram обработчики (добавлять сюда новые команды)
│   ├── start.py       # Базовые команды (/start, /help)  
│   ├── work_journal.py # ✅ Журнал работ (готов)
│   └── new_feature.py # 🆕 Новые фичи добавлять сюда
├── services/          # 💼 Бизнес-логика
│   ├── work_journal_service.py # ✅ Готовый сервис журнала
│   └── new_service.py # 🆕 Новые сервисы
├── database/          # 🗄️ Модели БД
│   ├── models.py      # Основные модели
│   ├── work_journal_models.py # ✅ Готовые модели журнала
│   └── database.py    # Подключение к БД
├── middleware/        # 🔧 Промежуточное ПО (редко трогать)
├── utils/            # 🛠️ Утилиты и помощники
└── integrations/     # 🔗 Внешние API
```

### 🎯 **Где что добавлять:**
- **Новые команды бота** → `app/handlers/new_feature.py`
- **Бизнес-логику** → `app/services/new_service.py`  
- **Модели БД** → `app/database/new_models.py`
- **Утилиты** → `app/utils/new_helper.py`

---

## 🛠️ КОМАНДЫ РАЗРАБОТКИ

### **Основные команды:**
```bash
make dev          # 🚀 Старт разработки (рекомендуемый)
make dev-restart  # ⚡ Быстрый перезапуск  
make dev-stop     # 🛑 Стоп разработки

make db-up        # 🗄️ Только база данных
make db-shell     # 💻 PostgreSQL консоль
make db-admin     # 🌐 pgAdmin (localhost:8080)

make bot-logs     # 📝 Логи бота в реальном времени
make status       # 📊 Статус всех сервисов
```

### **Тестирование:**
```bash
# Быстрые тесты
python test_basic.py          # Основные подключения
python test_work_journal.py   # Журнал работ

# Все тесты
make test
```

---

## 🆕 СОЗДАНИЕ НОВОЙ ФИЧИ

### **1. Создать обработчик:**
```python
# app/handlers/new_feature.py
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from ..utils.logger import bot_logger

router = Router()

@router.message(Command("new_command"))
async def handle_new_command(message: Message):
    """Обработчик новой команды"""
    bot_logger.info(f"New command called by user {message.from_user.id}")
    
    await message.reply("🆕 Новая фича работает!")
```

### **2. Подключить в main.py:**
```python
# app/main.py (добавить импорт и регистрацию)
from .handlers import new_feature

async def main():
    # ...существующий код...
    dp.include_router(new_feature.router)
    # ...остальной код...
```

### **3. Если нужна БД - создать модель:**
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

### **4. Создать миграцию:**
```bash
# В проекте уже настроен Alembic
docker exec -it telegram-bot-app alembic revision --autogenerate -m "Add new feature"
docker exec -it telegram-bot-app alembic upgrade head
```

---

## 💡 ГОТОВЫЕ ПРИМЕРЫ ДЛЯ КОПИРОВАНИЯ

### **Простая команда:**
```python
@router.message(Command("ping"))  
async def ping_command(message: Message):
    await message.reply("🏓 Pong!")
```

### **Команда с параметрами:**
```python
@router.message(Command("echo"))
async def echo_command(message: Message):
    text = message.text.replace('/echo ', '')
    await message.reply(f"📢 {text}")
```

### **Inline клавиатура:**
```python
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

@router.message(Command("menu"))
async def show_menu(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 Опция 1", callback_data="opt1")],
        [InlineKeyboardButton(text="⚡ Опция 2", callback_data="opt2")]
    ])
    await message.reply("Выберите опцию:", reply_markup=keyboard)

@router.callback_query(F.data == "opt1")
async def handle_option1(callback: CallbackQuery):
    await callback.message.edit_text("✅ Выбрана опция 1!")
```

### **Работа с БД (на примере журнала):**
```python
from sqlalchemy import select
from ..database.database import async_session
from ..database.work_journal_models import WorkJournalEntry

async def get_entries_for_user(user_id: int):
    """Получить записи пользователя"""
    async with async_session() as session:
        result = await session.execute(
            select(WorkJournalEntry).where(WorkJournalEntry.telegram_user_id == user_id)
        )
        return result.scalars().all()
```

---

## 🔧 ПОЛЕЗНЫЕ УТИЛИТЫ

### **Логирование:**
```python
from ..utils.logger import bot_logger

bot_logger.info("Информация")
bot_logger.warning("Предупреждение")
bot_logger.error("Ошибка")
```

### **Авторизация админа:**
```python
from ..middleware.auth import require_admin

@require_admin  # Декоратор - только для админов
async def admin_command(message: Message):
    await message.reply("👑 Админская команда!")
```

### **Форматирование (готовые утилиты):**
```python
from ..utils.work_journal_formatters import format_duration
from ..utils.formatters import escape_markdown

# Время: 90 минут → "1 час 30 минут"  
formatted_time = format_duration(90)

# Безопасный markdown
safe_text = escape_markdown("Текст с *спецсимволами*")
```

---

## 🗄️ БАЗА ДАННЫХ

### **Подключение:**
```python
from ..database.database import async_session

async def work_with_db():
    async with async_session() as session:
        # Ваша работа с БД
        pass
```

### **Готовые модели:**
- `User` - пользователи бота
- `WorkJournalEntry` - записи журнала работ  
- `WorkJournalWorker` - работники
- `WorkJournalCompany` - компании

### **Быстрые команды БД:**
```bash
make db-shell     # Подключиться к PostgreSQL
make db-backup    # Создать бэкап
make db-admin     # Открыть pgAdmin в браузере
```

---

## ⚙️ КОНФИГУРАЦИЯ

### **Добавить новые настройки:**
```python
# app/config.py
class Settings(BaseSettings):
    # ...существующие настройки...
    
    # Новая настройка
    new_feature_enabled: bool = False
    new_api_token: Optional[str] = None
    
    class Config:
        env_file = ".env"

# Использование
from ..config import settings
if settings.new_feature_enabled:
    # логика
```

### **В .env файле:**
```env
NEW_FEATURE_ENABLED=true
NEW_API_TOKEN=your_token_here
```

---

## 🚨 ОТЛАДКА И ОШИБКИ

### **Частые проблемы:**

#### **Бот не отвечает:**
```bash
make bot-logs  # Смотреть логи в реальном времени
```

#### **БД не подключается:**
```bash  
make db-up     # Запустить БД отдельно
make db-shell  # Проверить подключение
```

#### **Изменения не применяются:**
```bash
make dev-restart  # Перезапустить с новым кодом
```

### **Полезные логи:**
```bash
# Логи бота
make bot-logs

# Логи БД  
make db-logs

# Статус всех сервисов
make status
```

---

## 📝 ТЕСТИРОВАНИЕ ФИЧИ

### **1. Создать тестовый файл:**
```python
# test_new_feature.py
import asyncio
from app.handlers.new_feature import handle_new_command

async def test_new_feature():
    """Тест новой фичи"""
    print("🧪 Testing new feature...")
    # Ваши тесты
    print("✅ Feature working!")

if __name__ == "__main__":
    asyncio.run(test_new_feature())
```

### **2. Запустить:**
```bash
python test_new_feature.py
```

---

## 🎯 ГОТОВЫЕ ШАБЛОНЫ

### **Полный обработчик с БД:**
```python
# app/handlers/template.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy import select, insert, update, delete

from ..database.database import async_session
from ..database.models import User  # или ваша модель
from ..utils.logger import bot_logger
from ..middleware.auth import require_admin

router = Router()

@router.message(Command("template"))
async def template_command(message: Message):
    """Шаблонная команда с базой данных"""
    user_id = message.from_user.id
    bot_logger.info(f"Template command called by user {user_id}")
    
    try:
        async with async_session() as session:
            # Работа с БД
            result = await session.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                await message.reply("❌ Пользователь не найден")
                return
                
            # Создать клавиатуру
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Готово", callback_data="template_done")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="template_cancel")]
            ])
            
            await message.reply(
                f"🎯 Шаблон для {user.username}",
                reply_markup=keyboard
            )
            
    except Exception as e:
        bot_logger.error(f"Error in template command: {e}")
        await message.reply("❌ Произошла ошибка")

@router.callback_query(F.data.startswith("template_"))
async def handle_template_callback(callback: CallbackQuery):
    """Обработка кнопок шаблона"""
    action = callback.data.replace("template_", "")
    
    if action == "done":
        await callback.message.edit_text("✅ Выполнено!")
    elif action == "cancel":
        await callback.message.edit_text("❌ Отменено")
    
    await callback.answer()
```

---

## 🚀 РАЗВЕРТЫВАНИЕ ИЗМЕНЕНИЙ

### **Локальная разработка:**
```bash
# Во время разработки
make dev-restart  # Перезапуск с изменениями
```

### **Тестирование перед коммитом:**
```bash
python test_basic.py          # Основные тесты
python test_work_journal.py   # Тестирование модулей
make test                     # Все тесты
```

### **Коммит изменений:**
```bash
git add .
git commit -m "🆕 Add new feature: описание"  
git push origin main
```

---

## 🎊 ГОТОВО!

**Эти инструкции оптимизированы для быстрой разработки с Claude. Теперь мы можем:**

✅ **Быстро стартовать** - `make dev`  
✅ **Добавлять фичи** - копировать шаблоны  
✅ **Тестировать** - простые команды  
✅ **Отлаживать** - понятные логи  
✅ **Развертывать** - один Makefile  

---

*📅 Обновлено: Август 2025 для Claude Development*  
*🚀 Готов к быстрой разработке новых фич!*
