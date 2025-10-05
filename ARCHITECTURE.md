# 🏗️ Архитектура проекта

## Обзор

HHIVP IT Assistant Bot построен на **модульной архитектуре** с четким разделением ответственности и изоляцией компонентов.

## Ключевые принципы

### 🎯 Модульность
- Каждый модуль изолирован и независим
- Фильтры предотвращают конфликты между модулями
- Легкое добавление новых функций

### 🔒 Изоляция
- Фильтры состояний для work_journal
- Email фильтры для daily_tasks
- Приоритезация обработки сообщений

### 📊 Слоистая архитектура
```
┌─────────────────────────────────────┐
│             Telegram API            │ ← Внешний интерфейс
├─────────────────────────────────────┤
│              Роутеры                │ ← Маршрутизация
├─────────────────────────────────────┤
│             Обработчики             │ ← Логика команд
├─────────────────────────────────────┤
│             Middleware              │ ← Аутентификация, логи
├─────────────────────────────────────┤
│             Сервисы                 │ ← Бизнес-логика
├─────────────────────────────────────┤
│            База данных              │ ← Хранение данных
└─────────────────────────────────────┘
```

## Структура проекта

```
app/
├── main.py                    # 🚀 Точка входа
├── config.py                  # ⚙️ Конфигурация
├── modules/                   # 📦 Основные модули
│   ├── common/               # 🔧 Базовая функциональность
│   │   ├── __init__.py
│   │   ├── start.py          # /start, /help команды
│   │   └── profile.py        # Управление профилем
│   ├── daily_tasks/          # 📋 Ежедневные задачи
│   │   ├── __init__.py
│   │   ├── router.py         # Главный роутер
│   │   ├── handlers.py       # Команды (/settings, etc)
│   │   ├── text_handlers.py  # Email обработка
│   │   ├── filters.py        # Email фильтры
│   │   └── callbacks.py      # Callback кнопки
│   └── work_journal/         # 📝 Журнал работ
│       ├── __init__.py
│       ├── router.py         # Главный роутер
│       ├── handlers.py       # Команды (/journal, /history)
│       ├── text_handlers.py  # Текстовый ввод
│       ├── filters.py        # Фильтры состояний
│       └── callback_handlers.py # Callback обработка
├── services/                  # 💼 Бизнес-логика
│   ├── work_journal_service.py
│   ├── daily_tasks_service.py
│   ├── scheduler.py
│   └── n8n_integration_service.py
├── database/                  # 🗄️ Модели и БД
│   ├── database.py           # Подключение
│   ├── models.py             # Основные модели
│   └── work_journal_models.py # Модели журнала
├── middleware/                # 🔧 Промежуточное ПО
│   ├── auth.py               # Аутентификация
│   ├── logging.py            # Логирование
│   └── database.py           # Сессии БД
├── utils/                     # 🛠️ Утилиты
│   ├── logger.py             # Настройка логов
│   ├── work_journal_*.py     # Утилиты журнала
│   └── formatters.py         # Форматирование
└── integrations/             # 🔗 Внешние API
    ├── plane_api.py          # Plane.so интеграция
    └── n8n_webhook.py        # n8n webhook
```

## Поток обработки сообщений

### Приоритет модулей в main.py:
```python
# 1. COMMON - базовые команды (высший приоритет)
dp.include_router(start.router)

# 2. DAILY TASKS - email обработка (средний приоритет)
dp.include_router(daily_tasks_router)

# 3. WORK JOURNAL - состояния (низший приоритет)
dp.include_router(work_journal_router)
```

### Middleware цепочка:
```
Сообщение → Database → Performance → Logging → Auth → Обработчик
```

## Изоляция модулей

### Work Journal фильтры:
```python
class IsWorkJournalActiveFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        # Проверяет активное состояние в БД
        # Возвращает True только при активном состоянии
        return user_state and user_state != "idle"
```

### Daily Tasks фильтры:
```python
class IsAdminEmailFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        # Проверяет что сообщение - email от админа
        return is_email(message.text) and is_admin(message.from_user.id)
```

### Результат изоляции:
- ✅ **Email сообщения** → обрабатывает Daily Tasks
- ✅ **Текст при активном состоянии** → обрабатывает Work Journal
- ✅ **Команды** → обрабатывает соответствующий модуль
- ✅ **Конфликты исключены** → фильтры не пересекаются

## Управление состояниями

### Work Journal состояния:
```python
class WorkJournalState(Enum):
    IDLE = "idle"                    # Неактивное состояние
    SELECTING_DATE = "selecting_date"
    SELECTING_COMPANY = "selecting_company"
    ENTERING_DESCRIPTION = "entering_description"
    # ... другие состояния
```

### Хранение состояний:
```sql
CREATE TABLE user_work_journal_states (
    telegram_user_id BIGINT PRIMARY KEY,
    current_state VARCHAR(50),
    draft_data JSON,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

## База данных

### Основные таблицы:
- `bot_users` - пользователи бота
- `work_journal_entries` - записи журнала работ
- `work_journal_companies` - список компаний
- `user_work_journal_states` - состояния пользователей
- `admin_daily_tasks_settings` - настройки daily tasks
- `daily_tasks_logs` - логи задач

### Связи:
```
bot_users ←→ user_work_journal_states
bot_users ←→ work_journal_entries
bot_users ←→ admin_daily_tasks_settings
```

## Безопасность

### Уровни доступа:
- **Публичные команды**: /start, /help
- **Пользовательские**: /journal, /history
- **Админские**: /settings, email обработка

### Валидация:
- ✅ Все входные данные валидируются
- ✅ SQL injection защита через ORM
- ✅ Rate limiting через middleware
- ✅ Логирование всех действий

## Производительность

### Оптимизации:
- **Connection pooling** для БД
- **Redis кеширование** для сессий
- **Async/await** для всех операций
- **Middleware профилирование**

### Мониторинг:
- **PerformanceMiddleware** - время выполнения
- **Structured logging** - JSON логи
- **Error tracking** - все ошибки логируются

## Интеграции

### Plane.so API:
```python
class PlaneAPIClient:
    async def get_user_tasks(self, email: str) -> List[Task]:
        # Получение задач пользователя
    
    async def get_project_tasks(self, project_id: str) -> List[Task]:
        # Получение задач проекта
```

### n8n Webhook:
```python
class N8nIntegrationService:
    async def send_work_entry(self, entry: WorkJournalEntry):
        # Отправка записи в n8n для дальнейшей обработки
```

## Масштабирование

### Горизонтальное:
- Статeless обработчики
- Redis для состояний
- Load balancer ready

### Вертикальное:
- Настраиваемые пулы соединений
- Оптимизация запросов к БД
- Кеширование частых операций

## Тестирование

### Уровни тестов:
1. **Unit тесты** - отдельные функции
2. **Integration тесты** - модули с БД
3. **E2E тесты** - полные сценарии

### Изоляция в тестах:
```python
# Тест фильтров
async def test_work_journal_filter():
    filter_instance = IsWorkJournalActiveFilter()
    # Тестируем изолированно
```

## Развертывание

### Docker архитектура:
```yaml
services:
  telegram-bot:     # Основной бот
  postgres:         # База данных
  redis:           # Кеширование
  
networks:
  telegram-bot-network:  # Изолированная сеть
```

### Конфигурация:
- **Environment variables** для всех настроек
- **Docker secrets** для продакшена
- **Health checks** для мониторинга

## Мониторинг и логирование

### Структурированные логи:
```json
{
  "timestamp": "2025-08-08T20:44:12Z",
  "level": "INFO",
  "module": "work_journal",
  "action": "create_entry",
  "user_id": 123456,
  "execution_time": 0.45
}
```

### Метрики:
- Время ответа команд
- Использование памяти
- Количество активных пользователей
- Ошибки по модулям

Эта архитектура обеспечивает:
- ✅ **Надежность** - изоляция модулей
- ✅ **Масштабируемость** - легкое добавление функций
- ✅ **Поддерживаемость** - четкая структура
- ✅ **Безопасность** - многоуровневая защита
