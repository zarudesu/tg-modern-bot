# 🚀 Руководство по разработке Modern Telegram Bot

## 🏁 Быстрый старт

### 1. Подготовка окружения
```bash
# Клонирование репозитория
git clone <repository_url>
cd tg-mordern-bot

# Копирование и настройка переменных окружения
cp .env.example .env
# Отредактируйте .env файл со своими настройками

# Установка зависимостей (если планируете локальную разработку)
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
```

### 2. Настройка .env файла
```bash
# Telegram Bot Configuration
TELEGRAM_TOKEN=your_bot_token_here
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
ADMIN_USER_IDS=123456789,987654321  # ID админов через запятую

# Database Configuration
DATABASE_URL=postgresql+asyncpg://bot_user:bot_password@localhost:5432/telegram_bot
REDIS_URL=redis://:redis_password@localhost:6379/0

# Optional Integrations
VAULTWARDEN_URL=https://your-vaultwarden.com
OUTLINE_URL=https://your-outline.com
ZAMMAD_URL=https://your-zammad.com
ZAMMAD_TOKEN=your_zammad_token

# Logging Configuration
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### 3. Первый запуск
```bash
# Гибридный режим (рекомендуется для разработки)
make dev

# Или полный Docker режим
make full-up
```

## 🏗️ Добавление нового функционала

### Структура нового модуля
При добавлении нового функционала следуйте этой структуре:

```
app/
├── handlers/
│   └── your_module.py           # Обработчики команд и callbacks
├── database/
│   └── your_module_models.py    # Модели данных (если нужны)
├── services/
│   └── your_module_service.py   # Бизнес-логика и внешние API
└── utils/
    └── your_module_utils.py     # Вспомогательные функции
```

### Пример создания нового обработчика

#### 1. Создание обработчика (`app/handlers/example.py`)
```python
"""
Обработчики для примера модуля
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.database import get_async_session
from ..utils.logger import bot_logger, log_user_action
from ..services.example_service import ExampleService

router = Router()

@router.message(Command("example"))
async def example_command(message: Message):
    """Пример команды"""
    try:
        user_id = message.from_user.id
        log_user_action(user_id, "example")
        
        # Создание inline клавиатуры
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔧 Опция 1", callback_data="example_option1")],
            [InlineKeyboardButton(text="📊 Опция 2", callback_data="example_option2")],
        ])
        
        await message.answer(
            "🚀 *Пример модуля*\n\nВыберите действие:",
            reply_markup=keyboard,
            parse_mode="MarkdownV2"
        )
        
    except Exception as e:
        bot_logger.error(f"Example command error: {e}")
        await message.answer("❌ Произошла ошибка\\.", parse_mode="MarkdownV2")

@router.callback_query(F.data.startswith("example_"))
async def example_callbacks(callback: CallbackQuery):
    """Обработка callback запросов"""
    try:
        action = callback.data.replace("example_", "")
        user_id = callback.from_user.id
        
        async for session in get_async_session():
            service = ExampleService(session)
            
            if action == "option1":
                result = await service.handle_option1(user_id)
                await callback.message.edit_text(
                    f"✅ Выполнено: {result}",
                    parse_mode="MarkdownV2"
                )
            elif action == "option2":
                result = await service.handle_option2(user_id)
                await callback.message.edit_text(
                    f"📊 Результат: {result}",
                    parse_mode="MarkdownV2"
                )
        
        await callback.answer()
        
    except Exception as e:
        bot_logger.error(f"Example callback error: {e}")
        await callback.answer("❌ Ошибка при выполнении", show_alert=True)
```

#### 2. Создание сервиса (`app/services/example_service.py`)
```python
"""
Бизнес-логика для примера модуля
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from ..database.models import BotUser
from ..utils.logger import bot_logger

class ExampleService:
    """Сервис для работы с примером модуля"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def handle_option1(self, user_id: int) -> str:
        """Обработка первой опции"""
        try:
            # Получаем пользователя
            result = await self.session.execute(
                select(BotUser).where(BotUser.telegram_user_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return "Пользователь не найден"
            
            # Выполняем бизнес-логику
            bot_logger.info(f"User {user_id} executed option1")
            return f"Опция 1 выполнена для {user.first_name}"
            
        except Exception as e:
            bot_logger.error(f"Option1 error: {e}")
            raise
    
    async def handle_option2(self, user_id: int) -> str:
        """Обработка второй опции"""
        try:
            # Ваша бизнес-логика здесь
            bot_logger.info(f"User {user_id} executed option2")
            return "Статистика и аналитика"
            
        except Exception as e:
            bot_logger.error(f"Option2 error: {e}")
            raise
```

#### 3. Регистрация нового роутера (`app/main.py`)
```python
# Импорт нового роутера
from .handlers import start, example  # Добавляем example

# В функции main() добавляем регистрацию
dp.include_router(start.router)
dp.include_router(example.router)  # Добавляем эту строку
```

#### 4. Добавление команды в меню (`app/handlers/start.py`)
```python
# В конце файла обновляем COMMANDS_MENU
COMMANDS_MENU = [
    BotCommand(command="start", description="🚀 Начать работу с ботом"),
    BotCommand(command="help", description="❓ Справка по командам"),
    BotCommand(command="profile", description="👤 Мой профиль"),
    BotCommand(command="example", description="🔧 Пример модуля"),  # Новая команда
    BotCommand(command="ping", description="🏓 Проверка работоспособности"),
]
```

## 🗄️ Работа с базой данных

### Создание новой модели
```python
# app/database/example_models.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .models import Base

class ExampleEntity(Base):
    """Пример модели данных"""
    __tablename__ = "example_entities"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id = Column(BigInteger, ForeignKey("bot_users.telegram_user_id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Связи
    user = relationship("BotUser")
    
    # Индексы
    __table_args__ = (
        Index("idx_example_user_id", "telegram_user_id"),
        Index("idx_example_created_at", "created_at"),
    )
```

### Создание миграции
```bash
# Создание новой миграции
alembic revision --autogenerate -m "Add example entities"

# Применение миграции
alembic upgrade head
```

## 🔌 Интеграция с внешними сервисами

### Пример интеграции с внешним API
```python
# app/services/external_api_service.py
import aiohttp
from typing import Optional, Dict, Any
from ..utils.logger import bot_logger

class ExternalAPIService:
    """Сервис для работы с внешним API"""
    
    def __init__(self, base_url: str, token: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.headers = {}
        if token:
            self.headers['Authorization'] = f'Bearer {token}'
    
    async def make_request(self, endpoint: str, method: str = 'GET', data: Optional[Dict] = None) -> Dict[Any, Any]:
        """Выполнение HTTP запроса"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    json=data
                ) as response:
                    response.raise_for_status()
                    return await response.json()
                    
        except Exception as e:
            bot_logger.error(f"External API request failed: {e}")
            raise
```

## 🧪 Тестирование

### Структура тестов
```python
# tests/test_example.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.example_service import ExampleService

@pytest.mark.asyncio
async def test_example_service():
    """Тест сервиса примера"""
    # Мокаем сессию базы данных
    mock_session = AsyncMock()
    service = ExampleService(mock_session)
    
    # Тестируем функционал
    result = await service.handle_option1(123456)
    assert result is not None
```

### Запуск тестов
```bash
# Запуск всех тестов
make test

# Запуск конкретного теста
pytest tests/test_example.py -v

# Запуск с покрытием кода
pytest --cov=app tests/
```

## 🔧 Отладка

### Полезные команды для отладки
```bash
# Просмотр логов в реальном времени
make logs-bot

# Подключение к базе данных
make db-shell

# Проверка статуса всех сервисов
make status

# Просмотр логов конкретного контейнера
docker logs telegram_bot_db -f
```

### Отладка в IDE
Для отладки в PyCharm или VSCode:
1. Запустите базу данных: `make db-up`
2. Установите переменные окружения из `.env`
3. Запустите `app/main.py` в режиме отладки

## 📊 Мониторинг и профилирование

### Просмотр метрик производительности
```python
# В любом обработчике доступны метрики из PerformanceMiddleware
@router.message(Command("stats"))
async def stats_command(message: Message):
    # Метрики автоматически логируются middleware
    pass
```

### Анализ логов
```bash
# Поиск ошибок в логах
grep "ERROR" logs/bot.log

# Анализ производительности
grep "performance" logs/bot.log | tail -20
```

## 🚀 Deployment

### Продакшн развертывание
```bash
# Создание продакшн .env
cp .env.example .env.prod
# Настройте продакшн переменные

# Запуск в продакшн режиме
docker-compose -f docker-compose.yml --env-file .env.prod up -d
```

### Бэкапы
```bash
# Создание бэкапа базы данных
make db-backup

# Восстановление из бэкапа
make db-restore backup_file.sql
```

## 📝 Соглашения по коду

### Code Style
- Используйте **Black** для форматирования
- Следуйте **PEP 8**
- Добавляйте **type hints** ко всем функциям
- Документируйте все публичные методы

### Commit Messages
```
feat: добавлен модуль журнала работ
fix: исправлена ошибка в аутентификации
docs: обновлена документация по API
refactor: улучшена структура базы данных
```

### Именование
- **Файлы**: `snake_case.py`
- **Классы**: `PascalCase`
- **Функции/переменные**: `snake_case`
- **Константы**: `UPPER_SNAKE_CASE`
