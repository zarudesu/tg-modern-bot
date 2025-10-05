# Daily Tasks Module - Полная документация

## 🎯 Описание модуля

Daily Tasks - это модуль для ежедневной отправки задач из Plane API администраторам Telegram бота. 

### Основные функции:
- 📧 Настройка email для интеграции с Plane API
- ⏰ Установка времени ежедневных уведомлений
- 🔔 Включение/отключение уведомлений
- 📋 Просмотр текущих задач из Plane
- 🛠️ Тестирование подключения к Plane API

## 🏗️ Архитектура модуля

```
app/modules/daily_tasks/
├── __init__.py           # Инициализация модуля
├── handlers.py           # Команды (/daily_tasks, /daily_settings, /plane_test)
├── callback_handlers.py  # Callback обработчики для кнопок
├── email_handlers.py     # Обработка email ввода
└── filters.py           # Фильтры для изоляции модуля
```

### Связанные компоненты:
- `app/services/daily_tasks_service.py` - Основной сервис
- `app/integrations/plane_api.py` - Интеграция с Plane API
- `app/database/daily_tasks_models.py` - Модели БД

## 🚀 Команды пользователя

### `/daily_tasks`
Показывает текущие задачи админа из Plane
- Загружает задачи через Plane API
- Отображает до 5 задач с иконками статуса
- Кнопки: "Настройки", "Обновить"

### `/daily_settings` 
Настройки ежедневных уведомлений
- 📧 Email адрес (для Plane API)
- ⏰ Время уведомлений (09:00, 10:00, 11:00)
- 🔔 Включение/отключение уведомлений
- 📋 Показать текущие задачи

### `/plane_test`
Тестирование подключения к Plane API
- Проверяет конфигурацию API токена
- Тестирует доступность Plane сервера
- Показывает статус подключения

## 🔧 Техническая реализация

### Фильтрация сообщений
Модуль использует специальные фильтры для изоляции:

```python
class IsAdminEmailFilter(BaseFilter):
    """Фильтр email ТОЛЬКО от админов в состоянии ввода email"""
    
    async def __call__(self, message: Message) -> bool:
        # Проверяет что сообщение от админа
        # И админ находится в состоянии ввода email
        # И текст похож на email
        return is_valid_email and is_admin_waiting_for_email
```

### MarkdownV2 Экранирование
Все сообщения используют правильное экранирование:

```python
def escape_markdown_v2(text: str) -> str:
    chars_to_escape = ['_', '*', '[', ']', '(', ')', '~', '`', '>', 
                      '#', '+', '-', '=', '|', '{', '}', '.', '!', '@']
    for char in chars_to_escape:
        text = text.replace(char, f'\\\\{char}')
    return text
```

### Сохранение времени
Время конвертируется в Python time объект для PostgreSQL:

```python
from datetime import time as time_obj
hour, minute = map(int, time_str.split(':'))
time_object = time_obj(hour, minute)
```

## 🗄️ База данных

### Таблица admin_daily_tasks_settings
```sql
CREATE TABLE admin_daily_tasks_settings (
    id SERIAL PRIMARY KEY,
    telegram_user_id BIGINT NOT NULL,
    plane_email VARCHAR(255),
    enabled BOOLEAN DEFAULT false,
    notification_time TIME,
    timezone VARCHAR(50) DEFAULT 'Europe/Moscow',
    include_overdue BOOLEAN DEFAULT true,
    include_today BOOLEAN DEFAULT true,
    include_upcoming BOOLEAN DEFAULT true,
    group_by_project BOOLEAN DEFAULT true,
    max_tasks_per_section INTEGER DEFAULT 5,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    last_sent_at TIMESTAMP
);
```

## 🎛️ Конфигурация

### Переменные окружения (.env)
```bash
# Plane API настройки
PLANE_API_TOKEN=your_plane_api_token_here
PLANE_BASE_URL=https://your-plane-instance.com
PLANE_WORKSPACE_SLUG=your-workspace-slug

# Daily Tasks настройки
DAILY_TASKS_ENABLED=true
DAILY_TASKS_TIME=10:00
DAILY_TASKS_TIMEZONE=Europe/Moscow

# Admin IDs (через запятую)
ADMIN_USER_ID_LIST=28795547,123456789
```

## 🚨 Критические исправления

### 1. Инициализация daily_tasks_service
**Проблема:** `daily_tasks_service = None` при импорте
**Решение:** Проверка в email_handlers.py:
```python
if daily_tasks_service is None:
    bot_logger.error("КРИТИЧЕСКАЯ ОШИБКА: сервис не инициализирован")
    return
```

### 2. Формат времени в БД
**Проблема:** PostgreSQL не принимает строку времени
**Решение:** Конвертация в time объект:
```python
from datetime import time as time_obj
time_object = time_obj(hour, minute)
```

### 3. MarkdownV2 экранирование
**Проблема:** Символы не экранируются правильно
**Решение:** Двойной backslash `\\\\` для правильного экранирования

## 🧪 Тестирование

### Запуск тестов
```bash
./venv/bin/python test_daily_tasks_comprehensive.py
```

### Тестируемые компоненты:
1. ✅ Импорты всех модулей
2. ✅ MarkdownV2 экранирование
3. ✅ Конвертация времени
4. ✅ Инициализация DailyTasksService

## 🔍 Отладка

### Основные логи для мониторинга:
```
🎯 ADMIN EMAIL HANDLER TRIGGERED: email from admin_id
✅ Daily tasks service найден: <class 'DailyTasksService'>
📝 Создаем новые настройки для admin
📧 Устанавливаем email для admin
⏰ Конвертировали время в time объект
💾 Коммитим изменения в БД...
✅ Admin settings saved to database successfully
```

### Типичные ошибки:
1. `daily_tasks_service = None` - сервис не инициализирован
2. `'str' object has no attribute 'hour'` - неверный формат времени
3. `Character '.' is reserved` - неправильное MarkdownV2 экранирование

## 📋 Чек-лист для проверки

- [ ] Бот запускается без ошибок
- [ ] `daily_tasks_service` не равен None
- [ ] Email сохраняется в БД корректно
- [ ] Время сохраняется как time объект
- [ ] MarkdownV2 сообщения отправляются без ошибок
- [ ] Plane API подключение работает
- [ ] Задачи загружаются из Plane
- [ ] Все тесты проходят успешно

## 🎉 Использование

### Для админа (ID: 28795547):
1. `/start` - Начало работы с ботом
2. "📅 Настройки задач" - Переход к настройкам
3. "📧 Email адрес" - Ввод email для Plane
4. "⏰ Время уведомлений" - Установка времени
5. "🔔 Вкл/Выкл уведомления" - Включение уведомлений
6. "📋 Показать задачи" - Просмотр текущих задач

### Пример правильного flow:
```
Admin → /start → Кнопка "📅 Настройки задач" → 
"📧 Email адрес" → Ввод "zarudesu@gmail.com" → 
"⏰ Время уведомлений" → Выбор "🕙 10:00" → 
"🔔 Вкл/Выкл уведомления" → Включить → 
"📋 Показать задачи" → Просмотр задач из Plane
```

Модуль полностью готов к продакшену! 🚀