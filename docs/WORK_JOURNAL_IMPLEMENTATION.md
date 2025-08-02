# 📋 Модуль журнала работ - Руководство разработчика

## 🎯 Обзор

Модуль журнала работ предоставляет интерактивный интерфейс для записи выполненных работ через Telegram бота с автоматической синхронизацией в Google Sheets через n8n.

## 🏗️ Архитектура модуля

### Компоненты модуля

```
app/
├── database/
│   └── work_journal_models.py      # Модели данных
├── services/
│   ├── work_journal_service.py     # Бизнес-логика
│   └── n8n_integration_service.py  # Интеграция с n8n
├── handlers/
│   └── work_journal.py             # Обработчики команд
├── utils/
│   ├── work_journal_constants.py   # Константы и перечисления
│   ├── work_journal_formatters.py  # Форматирование сообщений
│   └── work_journal_keyboards.py   # Inline клавиатуры
└── sql/
    └── work_journal_migration.sql  # Миграция БД
```

### Схема базы данных

#### Основные таблицы

1. **`work_journal_entries`** - записи в журнале работ
2. **`user_work_journal_states`** - состояния пользователей при заполнении
3. **`work_journal_companies`** - предустановленные компании
4. **`work_journal_workers`** - предустановленные исполнители

## 🔧 Использование

### Команды бота

- `/journal` - начать создание записи
- `/history` - просмотр истории работ
- `/report` - отчеты и статистика

### Поток создания записи

1. **Выбор даты** (по умолчанию - сегодня)
2. **Выбор компании** (из предустановленного списка + свой вариант)
3. **Выбор длительности** (5 мин, 10 мин, 15 мин, 30 мин, 45 мин, 1 час, 1.5 часа, 2 часа + свой вариант)
4. **Ввод описания работ** (свободный текст)
5. **Выбор типа работ** (выезд/удаленно)
6. **Выбор исполнителя** (из предустановленного списка + свой вариант)
7. **Подтверждение и сохранение**

## 🛠️ API сервисов

### WorkJournalService

```python
from app.services.work_journal_service import WorkJournalService

async def example_usage():
    async for session in get_async_session():
        service = WorkJournalService(session)
        
        # Создание записи
        entry = await service.create_work_entry(
            telegram_user_id=123456789,
            user_email="user@example.com",
            work_date=date.today(),
            company="Компания",
            work_duration="30 мин",
            work_description="Описание работ",
            is_travel=True,
            worker_name="Исполнитель"
        )
        
        # Получение записей с фильтрами
        entries = await service.get_work_entries(
            telegram_user_id=123456789,
            date_from=date.today() - timedelta(days=7),
            company="Компания",
            limit=10
        )
        
        # Статистика
        stats = await service.get_statistics(
            telegram_user_id=123456789,
            date_from=date.today() - timedelta(days=30)
        )
```

### N8nIntegrationService

```python
from app.services.n8n_integration_service import N8nIntegrationService

async def example_n8n():
    n8n_service = N8nIntegrationService()
    
    # Тест соединения
    success, message = await n8n_service.test_connection()
    
    # Отправка записи
    user_data = {"first_name": "John", "username": "john_doe"}
    success, error = await n8n_service.send_work_entry(entry, user_data)
```

## 🔌 Настройка n8n интеграции

### Переменные окружения

```bash
# n8n Integration
N8N_WEBHOOK_URL=https://your-n8n-instance.com/webhook/work-journal
N8N_WEBHOOK_SECRET=your_webhook_secret_key

# Google Sheets
GOOGLE_SHEETS_ID=your_google_sheets_id_here
```

### Структура webhook данных

```json
{
    "source": "telegram_bot",
    "event_type": "work_journal_entry",
    "timestamp": "2025-07-31T12:34:56Z",
    "data": {
        "entry_id": 123,
        "user": {
            "telegram_id": 123456789,
            "email": "user@example.com",
            "first_name": "John",
            "username": "john_doe"
        },
        "work_entry": {
            "date": "2025-07-31",
            "company": "Компания",
            "duration": "30 мин",
            "description": "Описание работ",
            "is_travel": true,
            "worker": "Исполнитель"
        }
    }
}
```

## 📊 Мониторинг и отладка

### Логирование

Все действия логируются с уровнями:
- `INFO` - успешные операции
- `WARNING` - предупреждения (например, n8n недоступен)
- `ERROR` - ошибки выполнения

### Статусы синхронизации n8n

- `pending` - ожидает отправки
- `success` - успешно отправлено
- `failed` - ошибка отправки (после всех попыток)

### Мониторинг через SQL

```sql
-- Записи с ошибками синхронизации
SELECT * FROM work_journal_entries 
WHERE n8n_sync_status = 'failed' 
ORDER BY created_at DESC;

-- Статистика по статусам
SELECT n8n_sync_status, COUNT(*) 
FROM work_journal_entries 
GROUP BY n8n_sync_status;
```

## 🧪 Тестирование

### Запуск тестов

```bash
cd /Users/zardes/Projects/tg-mordern-bot
python test_work_journal.py
```

### Тестируемые компоненты

1. Инициализация базы данных
2. Создание и управление состояниями пользователей
3. CRUD операции с записями
4. Статистика и отчеты
5. Форматирование сообщений
6. Создание клавиатур
7. n8n интеграция

## 🐛 Устранение неполадок

### Частые проблемы

#### 1. Ошибки синхронизации с n8n

**Проблема**: Записи остаются в статусе `pending`

**Решение**:
1. Проверить настройки `N8N_WEBHOOK_URL` и `N8N_WEBHOOK_SECRET`
2. Проверить доступность n8n сервера
3. Просмотреть логи: `docker logs telegram-bot-app`

#### 2. Состояние пользователя "застряло"

**Проблема**: Пользователь не может завершить создание записи

**Решение**:
```sql
-- Очистить состояние пользователя
UPDATE user_work_journal_states 
SET current_state = 'idle', 
    draft_date = NULL,
    draft_company = NULL,
    draft_duration = NULL,
    draft_description = NULL,
    draft_is_travel = NULL,
    draft_worker = NULL
WHERE telegram_user_id = 123456789;
```

#### 3. Пустой список компаний/исполнителей

**Проблема**: Не отображаются предустановленные компании

**Решение**:
```python
# Переинициализация дефолтных данных
from app.services.work_journal_service import init_default_data

async for session in get_async_session():
    await init_default_data(session)
```

### Диагностические запросы

```sql
-- Состояния пользователей
SELECT telegram_user_id, current_state, updated_at 
FROM user_work_journal_states 
WHERE current_state != 'idle';

-- Последние записи
SELECT * FROM work_journal_entries 
ORDER BY created_at DESC LIMIT 10;

-- Статистика по компаниям
SELECT company, COUNT(*) as entries_count 
FROM work_journal_entries 
GROUP BY company 
ORDER BY entries_count DESC;
```

## 🔄 Миграции

### Применение миграции

```bash
# В контейнере PostgreSQL
psql -U bot_user -d telegram_bot -f /app/sql/work_journal_migration.sql
```

### Откат миграции

```sql
-- Удаление таблиц (ОСТОРОЖНО!)
DROP TABLE IF EXISTS work_journal_entries CASCADE;
DROP TABLE IF EXISTS user_work_journal_states CASCADE;
DROP TABLE IF EXISTS work_journal_companies CASCADE;
DROP TABLE IF EXISTS work_journal_workers CASCADE;
```

## 📈 Расширение функциональности

### Добавление новых полей

1. Обновить модель в `work_journal_models.py`
2. Создать миграцию БД
3. Обновить состояния в `work_journal_constants.py`
4. Добавить обработку в `work_journal.py`
5. Обновить форматтеры и клавиатуры

### Добавление новых отчетов

1. Расширить `WorkJournalService.get_statistics()`
2. Добавить новые действия в `CallbackAction`
3. Создать обработчики в `work_journal.py`
4. Добавить форматтеры для новых отчетов

### Кастомизация интеграций

1. Создать новый сервис интеграции по аналогии с `N8nIntegrationService`
2. Добавить вызов в обработчик сохранения записи
3. Добавить настройки в `config.py`

## 🔗 Полезные ссылки

- [Документация aiogram](https://docs.aiogram.dev/)
- [SQLAlchemy Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [n8n Webhooks](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/)
- [Google Sheets API](https://developers.google.com/sheets/api)
