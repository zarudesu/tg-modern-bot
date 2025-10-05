# 🔧 Руководство разработчика - МОДУЛЬНАЯ АРХИТЕКТУРА

## 🏗️ АРХИТЕКТУРА ПОСЛЕ РЕФАКТОРИНГА

### 📁 **Структура проекта:**
```
app/
├── modules/           # 🎯 ГЛАВНЫЕ МОДУЛИ БОТА (основная разработка)
│   ├── daily_tasks/   # ✅ Ежедневные задачи (email приоритет)
│   ├── work_journal/  # ✅ Журнал работ (состояния активности)
│   └── your_module/   # 🆕 НОВЫЕ МОДУЛИ СОЗДАВАТЬ ЗДЕСЬ
├── handlers/          # 🔧 Общие обработчики (start, help, admin)
├── services/          # 💼 Бизнес-логика
├── database/          # 🗄️ Модели БД
├── middleware/        # 🔧 Промежуточное ПО
├── utils/            # 🛠️ Утилиты и помощники
└── integrations/     # 🔗 Внешние API
```

### 🎯 **КРИТИЧЕСКИЕ ПРИНЦИПЫ:**
1. **Изоляция модулей** - каждый модуль обрабатывает только свои сообщения
2. **Фильтры приоритетов** - email → daily_tasks, текст при активности → work_journal
3. **Порядок загрузки** - в main.py порядок роутеров определяет приоритеты
4. **Состояния модулей** - используй БД для хранения активных состояний

## 🆕 СОЗДАНИЕ НОВОГО МОДУЛЯ

### **Шаг 1: Структура модуля**
```
app/modules/your_module/
├── __init__.py        # Экспорт router
├── router.py          # 🎯 ГЛАВНЫЙ роутер (подключает все)
├── handlers.py        # 📋 Команды (/your_command)
├── filters.py         # 🔍 Фильтры изоляции (ОБЯЗАТЕЛЬНО!)
├── text_handlers.py   # 📝 Обработка текста (с фильтрами)
└── callback_handlers.py # 🎛 Кнопки и коллбэки
```

### **Шаг 2: Шаблон модуля**

**`__init__.py`:**
```python
from .router import router
__all__ = ['router']
```

**`router.py`:**
```python
from aiogram import Router
from .handlers import router as handlers_router
from .text_handlers import router as text_router
from .callback_handlers import router as callback_router

router = Router()

# ПОРЯДОК ВАЖЕН:
router.include_router(handlers_router)     # Команды первые
router.include_router(callback_router)     # Коллбэки вторые  
router.include_router(text_router)         # Текст последний
```

**`filters.py`:**
```python
from aiogram.filters import BaseFilter
from aiogram.types import Message
from ...database.database import get_async_session

class YourModuleActiveFilter(BaseFilter):
    """Фильтр для активного состояния модуля"""
    
    async def __call__(self, message: Message) -> bool:
        user_id = message.from_user.id
        
        # Проверяем активное состояние в БД
        async for session in get_async_session():
            # Замени на свою логику проверки состояния
            user_state = await get_user_state(session, user_id, 'your_module')
            return user_state and user_state.active
```

**`handlers.py`:**
```python
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

router = Router()

@router.message(Command("your_command"))
async def your_command_handler(message: Message):
    """Команда вашего модуля"""
    await message.reply("🎯 Ваш модуль работает!")
```

**`text_handlers.py`:**
```python
from aiogram import Router, F
from aiogram.types import Message
from .filters import YourModuleActiveFilter

router = Router()

@router.message(F.text, YourModuleActiveFilter())
async def handle_text_input(message: Message):
    """Обработка текста только при активном состоянии"""
    text = message.text.strip()
    
    # Ваша логика обработки текста
    await message.reply(f"📝 Получен текст: {text}")
```

### **Шаг 3: Подключение в main.py**
```python
# В app/main.py добавить:
from .modules.your_module.router import router as your_module_router

# В функции main():
dp.include_router(your_module_router)
```

## 🔍 ФИЛЬТРЫ ИЗОЛЯЦИИ

### **Типы фильтров:**

**Email фильтр (приоритет):**
```python
class EmailFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return bool(re.match(r'^[^@]+@[^@]+\.[^@]+$', message.text or ''))
```

**Состояние активности:**
```python
class ActiveStateFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        # Проверка в БД что у пользователя активное состояние модуля
        user_id = message.from_user.id
        return await check_active_state(user_id, 'module_name')
```

**Комбинированный фильтр:**
```python
class AdminEmailFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return (is_email(message.text) and 
                is_admin(message.from_user.id))
```

## 📊 ПРИМЕРЫ ГОТОВЫХ МОДУЛЕЙ

### **daily_tasks модуль:**
- **Приоритет**: Высший (email админов)
- **Фильтр**: `IsAdminEmailFilter` 
- **Обрабатывает**: email от админов для настройки Plane

### **work_journal модуль:**
- **Приоритет**: Низкий (только активные состояния)
- **Фильтр**: `IsWorkJournalActiveFilter`
- **Обрабатывает**: текст только при активных командах журнала

## 🚀 ДЕПЛОЙ И ТЕСТИРОВАНИЕ

### **Разработка:**
```bash
make dev              # Запуск в dev режиме
make dev-restart      # Перезапуск с изменениями
```

### **Тестирование модуля:**
```bash
python test_your_module.py  # Создать тест модуля
python test_isolation.py    # Тест изоляции
```

### **Продакшн:**
```bash
make prod-deploy      # Деплой на сервер
```

## 🛡️ ВАЖНЫЕ ПРАВИЛА

1. **ВСЕГДА используй фильтры** - модуль должен обрабатывать только свои сообщения
2. **Порядок роутеров важен** - первый зарегистрированный имеет приоритет
3. **Тестируй изоляцию** - убедись что модули не конфликтуют
4. **Состояния в БД** - для текстового ввода используй состояния пользователя
5. **Архивируй старое** - не удаляй, а перемещай в archive/

## 📝 ЧЕКЛИСТ НОВОГО МОДУЛЯ

- [ ] Создана структура папок в `app/modules/your_module/`
- [ ] Написан `router.py` с правильным порядком подключения
- [ ] Созданы фильтры изоляции в `filters.py`
- [ ] Команды работают в `handlers.py`
- [ ] Текстовые обработчики с фильтрами в `text_handlers.py`
- [ ] Подключен роутер в `main.py`
- [ ] Протестирована изоляция от других модулей
- [ ] Создан тест модуля
