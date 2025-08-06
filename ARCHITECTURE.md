# 🏗️ Архитектура независимой разработки

```
┌─────────────────────────────────────────────────────────────────┐
│                    🤖 TELEGRAM BOT ECOSYSTEM                    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│   🤖 BOT SERVICE    │    │  🗄️ DATABASE SERVICE │    │  🔄 CACHE SERVICE   │
├─────────────────────┤    ├─────────────────────┤    ├─────────────────────┤
│ • Telegram Bot      │◄──►│ • PostgreSQL 15     │    │ • Redis 7           │
│ • Python 3.11       │    │ • Auto-migrations   │◄──►│ • Session storage   │
│ • aiogram 3.7       │    │ • SQL initialization│    │ • Rate limiting     │
│ • Async/await       │    │ • Proper indexes    │    │ • Caching           │
│                     │    │ • Triggers & funcs  │    │                     │
├─────────────────────┤    ├─────────────────────┤    ├─────────────────────┤
│ 🚀 Development:     │    │ 🔌 Connections:     │    │ 🔌 Connections:     │
│ • Local Python      │    │ • localhost:5432    │    │ • localhost:6379    │
│ • Docker container  │    │ • Docker network    │    │ • Docker network    │
│ • Hot reload        │    │ • Internal comms    │    │ • Password auth     │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
          │                          │                          │
          │                          │                          │
          └──────────────────────────┼──────────────────────────┘
                                     │
                 ┌─────────────────────────────────────────┐
                 │        🌐 ADMIN INTERFACES               │
                 ├─────────────────────────────────────────┤
                 │ • pgAdmin (localhost:8080)              │
                 │ • Database management                   │
                 │ • Query execution                       │
                 │ • Visual schema browser                 │
                 └─────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                     🔧 DEVELOPMENT MODES                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ 1️⃣ ГИБРИДНЫЙ (рекомендуется)                                    │
│    make dev                                                     │
│    ├── 🗄️ База данных: Docker контейнеры                        │
│    └── 🤖 Бот: локальный Python процесс                         │
│                                                                 │
│ 2️⃣ ПОЛНЫЙ DOCKER                                                │
│    make full-up                                                 │
│    ├── 🗄️ База данных: Docker контейнеры                        │
│    └── 🤖 Бот: Docker контейнер                                 │
│                                                                 │
│ 3️⃣ НЕЗАВИСИМЫЙ                                                  │
│    make db-up && make bot-up                                    │
│    ├── 🗄️ База данных: отдельные контейнеры                     │
│    └── 🤖 Бот: отдельный контейнер                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    📊 DATA FLOW & CONNECTIONS                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ 🔄 Database Connection Flow:                                    │
│    Bot ──► PostgreSQL://bot_user:***@localhost:5432/telegram_bot│
│    Bot ──► Redis://***@localhost:6379/0                        │
│                                                                 │
│ 📨 Message Processing Flow:                                     │
│    Telegram ──► Bot ──► Auth Middleware ──► Handler ──► Database│
│                  │                                              │
│                  └──► Logging Middleware ──► Logs ──► Database  │
│                                                                 │
│ 🔐 Authentication Flow:                                         │
│    User Message ──► AuthMiddleware ──► Database ──► Role Check  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 🎯 Преимущества архитектуры

### ✅ **Независимая разработка**
- Каждый сервис можно разрабатывать отдельно
- База данных изолирована от изменений кода
- Быстрый цикл разработки без пересборки контейнеров

### ✅ **Масштабируемость**
- Готовность к микросервисной архитектуре
- Легко добавлять новые сервисы
- Горизонтальное масштабирование

### ✅ **Надёжность**
- Изоляция компонентов
- Автоматические health checks
- Graceful shutdown

### ✅ **Удобство разработки**
- Множество режимов запуска
- Подробные логи и мониторинг
- Веб-интерфейсы для управления

## 🚀 Команды для ежедневной работы

```bash
# Быстрый старт разработки
make dev                # БД в Docker, бот локально

# Управление базой данных
make db-up              # Запустить БД
make db-shell           # PostgreSQL консоль
make db-admin           # Веб-интерфейс pgAdmin

# Тестирование и отладка
make test               # Запустить тесты
make status             # Статус всех контейнеров
make logs               # Все логи

# Очистка и сброс
make clean              # Очистить временные файлы
make full-clean         # Полная очистка всех данных
```
8n_integration_service.py`

**Функциональность:**
- 📤 Отправка webhook при создании записи
- 🔄 Retry механизм при ошибках
- 📊 Отслеживание статуса синхронизации
- 🔒 Безопасная передача данных

**Структура webhook:**
```json
{
  "source": "telegram_bot",
  "event_type": "work_journal_entry",
  "timestamp": "2025-08-03T15:30:45Z",
  "data": {
    "entry_id": 123,
    "user": {
      "telegram_id": 123456789,
      "email": "admin@company.com",
      "first_name": "Admin"
    },
    "work_entry": {
      "date": "2025-08-03",
      "company": "Ива",
      "duration": "45 мин",
      "description": "Настройка сервера",
      "is_travel": false,
      "workers": ["Тимофей", "Дима"],
      "workers_count": 2
    }
  }
}
```

### 📊 **Google Sheets (через n8n)**
**Автоматическое сохранение:**
- Каждая запись отправляется в n8n
- n8n обрабатывает и сохраняет в Google Sheets
- Структурированный формат данных
- Информация о создателе и исполнителях

### 🛠️ **Plane Integration**
**Компонент:** `app/integrations/plane_with_mentions.py`

**Функциональность:**
- 📝 Создание задач в Plane
- 👥 Упоминания пользователей в комментариях
- 🔄 Синхронизация статусов
- 📊 Отчеты по задачам

---

## 🔄 Жизненный цикл запроса

### 📝 **Пример: Создание записи в журнале работ**

```mermaid
sequenceDiagram
    participant U as User
    participant TG as Telegram
    participant MW as Middleware
    participant H as Handler
    participant S as Service
    participant DB as Database
    participant N8N as n8n
    participant GS as Google Sheets

    U->>TG: /journal
    TG->>MW: Incoming message
    MW->>MW: Auth check
    MW->>MW: Logging
    MW->>H: Route to handler
    H->>S: Get user state
    S->>DB: Query user state
    DB-->>S: Return state
    S-->>H: Return state
    H->>H: Create keyboard
    H-->>TG: Send date selection
    TG-->>U: Show keyboard
    
    U->>TG: Select date
    TG->>H: Callback query
    H->>S: Update state
    S->>DB: Save state
    H-->>TG: Send company selection
    
    Note over U,GS: User fills all fields...
    
    U->>TG: Confirm entry
    TG->>H: Final callback
    H->>S: Create entry
    S->>DB: Save to database
    S->>N8N: Send webhook
    N8N->>GS: Save to Sheets
    S->>S: Mention workers
    S-->>H: Return success
    H-->>TG: Send confirmation
    TG-->>U: Show success message
```

---

## 🗄️ Структура базы данных

### 📊 **ER диаграмма основных таблиц:**

```sql
┌─────────────────────┐     ┌─────────────────────┐
│     bot_users       │────▶│   message_logs      │
├─────────────────────┤     ├─────────────────────┤
│ id (PK)            │     │ id (PK)            │
│ telegram_user_id   │     │ telegram_user_id   │
│ username           │     │ chat_id            │
│ first_name         │     │ message_type       │
│ role               │     │ text_content       │
│ is_active          │     │ created_at         │
│ created_at         │     └─────────────────────┘
│ settings (JSON)    │              
└─────────────────────┘              
         │                          
         ▼                          
┌─────────────────────┐     ┌─────────────────────┐
│work_journal_entries │     │ work_journal_workers│
├─────────────────────┤     ├─────────────────────┤
│ id (PK)            │     │ id (PK)            │
│ telegram_user_id   │     │ name               │
│ work_date          │     │ telegram_username  │
│ company            │     │ telegram_user_id   │
│ work_duration      │     │ mention_enabled    │
│ work_description   │     │ is_active          │
│ is_travel          │     └─────────────────────┘
│ worker_names (JSON)│              
│ created_by_user_id │              
│ n8n_sync_status    │              
└─────────────────────┘              
```

### 🔍 **Индексы для оптимизации:**

```sql
-- Основные индексы для быстрого поиска
CREATE INDEX idx_work_journal_date ON work_journal_entries(work_date);
CREATE INDEX idx_work_journal_user_id ON work_journal_entries(telegram_user_id);
CREATE INDEX idx_work_journal_company ON work_journal_entries(company);
CREATE INDEX idx_work_journal_sync_status ON work_journal_entries(n8n_sync_status);

-- Составные индексы для сложных запросов
CREATE INDEX idx_work_journal_date_user ON work_journal_entries(work_date, telegram_user_id);
CREATE INDEX idx_work_journal_created_by ON work_journal_entries(created_by_user_id);
```

---

## ⚡ Производительность и масштабируемость

### 📊 **Метрики производительности:**

| Операция | Время отклика | Оптимизация |
|----------|---------------|-------------|
| `/start` | < 50ms | Кэширование в Redis |
| `/journal` | < 100ms | Предзагрузка данных |
| Создание записи | < 500ms | Асинхронные операции |
| `/history` поиск | < 200ms | Индексы БД |
| `/report` генерация | < 1s | Агрегационные запросы |

### 🔧 **Стратегии оптимизации:**

#### **1. База данных:**
- ✅ **Индексы** на часто запрашиваемые поля
- ✅ **Connection pooling** через SQLAlchemy
- ✅ **Асинхронные запросы** с asyncpg
- ✅ **Batch operations** для массовых операций

#### **2. Кэширование:**
- ✅ **Redis** для сессий пользователей
- ✅ **Кэширование состояний** диалогов
- ✅ **Rate limiting** в Redis
- ✅ **Временное хранение** обработанных данных

#### **3. Архитектурные решения:**
- ✅ **Асинхронность** на всех уровнях
- ✅ **Lazy loading** связанных данных
- ✅ **Пагинация** для больших результатов
- ✅ **Graceful degradation** при ошибках

---

## 🔒 Безопасность

### 🛡️ **Уровни защиты:**

#### **1. Аутентификация:**
```python
class AuthMiddleware:
    async def __call__(self, handler, event, data):
        user_id = event.from_user.id
        if not settings.is_admin(user_id):
            await event.answer("❌ Доступ запрещен")
            return
        return await handler(event, data)
```

#### **2. Валидация данных:**
```python
class WorkEntryData(BaseModel):
    date: date
    company: str = Field(min_length=1, max_length=255)
    duration: str = Field(regex=r'^\d+\s*(мин|час).*$')
    description: str = Field(min_length=1, max_length=2000)
    is_travel: bool
    workers: List[str] = Field(min_items=1)
```

#### **3. SQL Injection защита:**
- ✅ **SQLAlchemy ORM** - параметризованные запросы
- ✅ **Валидация входных данных** через Pydantic
- ✅ **Типизация** всех параметров запросов

#### **4. Rate Limiting:**
```python
# Ограничения по типам операций
RATE_LIMITS = {
    'default': '10/minute',
    'search': '30/minute', 
    'admin': '100/minute'
}
```

---

## 🐳 Docker архитектура

### 📦 **Контейнеризация:**

```yaml
# docker-compose.yml структура
version: '3.8'
services:
  bot:                    # Python бот
    build: .
    depends_on: [db, redis]
    environment: [...]
    
  db:                     # PostgreSQL 15
    image: postgres:15
    volumes: [postgres_data:/var/lib/postgresql/data]
    
  redis:                  # Redis 7 
    image: redis:7
    command: redis-server --appendonly yes
    
  pgadmin:               # Веб-интерфейс БД
    image: dpage/pgadmin4
    depends_on: [db]
```

### 🔄 **Сетевая архитектура:**
```
┌─────────────────────┐
│   External Network  │
│  (Telegram API)     │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│    Bot Container    │
│   (Python App)     │
└──────────┬──────────┘
           │
    ┌──────▼──────┐
    │   Internal  │
    │   Network   │
    │             │
┌───▼───┐    ┌───▼───┐
│  DB   │    │ Redis │
│       │    │       │
└───────┘    └───────┘
```

---

## 🔄 Состояния и FSM

### 🎭 **Finite State Machine для диалогов:**

```python
class JournalStates(StatesGroup):
    waiting_for_date = State()
    waiting_for_company = State() 
    waiting_for_duration = State()
    waiting_for_description = State()
    waiting_for_travel_type = State()
    waiting_for_workers = State()
    waiting_for_confirmation = State()
```

### 📊 **Диаграмма состояний:**

```mermaid
stateDiagram-v2
    [*] --> waiting_for_date : /journal command
    waiting_for_date --> waiting_for_company : date selected
    waiting_for_company --> waiting_for_duration : company selected
    waiting_for_duration --> waiting_for_description : duration selected
    waiting_for_description --> waiting_for_travel_type : description entered
    waiting_for_travel_type --> waiting_for_workers : travel type selected
    waiting_for_workers --> waiting_for_confirmation : workers selected
    waiting_for_confirmation --> [*] : entry confirmed
    waiting_for_confirmation --> waiting_for_date : edit requested
```

---

## 📈 Мониторинг и логирование

### 📊 **Система логирования:**

```python
# Уровни логирования
LOGGING_LEVELS = {
    'DEBUG': 'Детальная отладочная информация',
    'INFO': 'Общая информация о работе',
    'WARNING': 'Предупреждения',
    'ERROR': 'Ошибки выполнения',
    'CRITICAL': 'Критические ошибки'
}
```

### 📈 **Типы метрик:**
- ⏱️ **Performance metrics** - время выполнения операций
- 👥 **User metrics** - активность пользователей  
- 📊 **Business metrics** - статистика по записям
- 🔧 **System metrics** - использование ресурсов

### 🔍 **Health Checks:**
```python
async def health_check():
    """Проверка состояния всех компонентов"""
    checks = {
        'database': await check_database(),
        'redis': await check_redis(),
        'telegram_api': await check_telegram(),
        'n8n_webhook': await check_n8n()
    }
    return all(checks.values())
```

---

## 🚀 Развертывание и CI/CD

### 🔄 **Стратегия развертывания:**

```bash
# Режимы развертывания
Development:  make dev     # Локальная разработка
Staging:      make stage   # Тестовое окружение  
Production:   make prod    # Продакшн развертывание
```

### 📦 **Build процесс:**
1. **Тестирование** - запуск всех тестов
2. **Линтинг** - проверка качества кода
3. **Сборка образа** - Docker build
4. **Миграции БД** - применение изменений схемы
5. **Развертывание** - запуск новой версии
6. **Health checks** - проверка работоспособности

---

## 🔮 Будущее развитие

### 📋 **Architectural Roadmap:**

#### **v1.2 - Ближайшие улучшения:**
- 🌐 **REST API** для внешних интеграций
- 📊 **GraphQL** для гибких запросов данных
- 🔄 **Event Sourcing** для аудита изменений
- 📱 **WebSocket** для real-time уведомлений

#### **v2.0 - Масштабные изменения:**
- 🏗️ **Микросервисная архитектура**
- 📦 **Kubernetes deployment**
- 🔄 **Message queues** (RabbitMQ/Kafka)
- 🌍 **Multi-region deployment**

### 🎯 **Принципы развития:**
- ✅ **Backward compatibility** - совместимость с предыдущими версиями
- ✅ **Incremental updates** - постепенные улучшения
- ✅ **Zero-downtime deployment** - развертывание без простоев
- ✅ **Feature flags** - постепенное включение функций

---

## 🏆 Заключение

### ✅ **Архитектурные преимущества:**

**🏗️ Модульность:**
- Четкое разделение ответственности
- Независимые компоненты
- Легкое тестирование и отладка

**⚡ Производительность:**
- Асинхронная архитектура
- Оптимизированные запросы к БД
- Эффективное кэширование

**🔒 Безопасность:**
- Многоуровневая аутентификация
- Валидация всех входных данных
- Полное логирование действий

**📈 Масштабируемость:**
- Готовность к горизонтальному масштабированию
- Микросервисная готовность
- Эффективное использование ресурсов

### 🎯 **Готовность к продакшн:**
Архитектура спроектирована с учетом production требований и готова к развертыванию в любом окружении от небольших команд до крупных enterprise систем.

---

*📅 Обновлено: 3 августа 2025*  
*🏗️ Версия архитектуры: 1.1.0*  
*📊 Статус: Production Ready*