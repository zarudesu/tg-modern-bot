# 🛠️ ТЕХНИЧЕСКАЯ СПЕЦИФИКАЦИЯ - HHIVP Telegram Bot

## 📋 API Endpoints Mapping

### NetBox API Endpoints
```python
NETBOX_ENDPOINTS = {
    'devices': '/api/dcim/devices/',
    'sites': '/api/dcim/sites/',
    'device_types': '/api/dcim/device-types/',
    'manufacturers': '/api/dcim/manufacturers/',
    'racks': '/api/dcim/racks/',
    'interfaces': '/api/dcim/interfaces/',
    'ip_addresses': '/api/ipam/ip-addresses/',
    'prefixes': '/api/ipam/prefixes/',
    'vlans': '/api/ipam/vlans/',
    'cables': '/api/dcim/cables/',
}
```

### Vaultwarden API Endpoints
```python
VAULTWARDEN_ENDPOINTS = {
    'login': '/identity/connect/token',
    'sync': '/api/sync',
    'ciphers': '/api/ciphers',
    'organizations': '/api/organizations',
    'collections': '/api/organizations/{org_id}/collections',
}
```

### Outline API Endpoints
```python
OUTLINE_ENDPOINTS = {
    'collections': '/api/collections.list',
    'documents': '/api/documents.list',
    'search': '/api/documents.search',
    'document_info': '/api/documents.info',
}
```

### Zammad API Endpoints
```python
ZAMMAD_ENDPOINTS = {
    'tickets': '/api/v1/tickets',
    'users': '/api/v1/users',
    'groups': '/api/v1/groups',
    'ticket_states': '/api/v1/ticket_states',
    'priorities': '/api/v1/ticket_priorities',
}
```

## 🗄️ Структура базы данных

### Таблица: bot_users
```sql
CREATE TABLE bot_users (
    id SERIAL PRIMARY KEY,
    telegram_user_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'guest',
    is_active BOOLEAN DEFAULT true,
    language_code VARCHAR(10) DEFAULT 'ru',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    settings JSONB DEFAULT '{}'
);
```

### Таблица: message_logs
```sql
CREATE TABLE message_logs (
    id SERIAL PRIMARY KEY,
    telegram_message_id BIGINT NOT NULL,
    telegram_user_id BIGINT NOT NULL,
    chat_id BIGINT NOT NULL,
    chat_type VARCHAR(50) NOT NULL,
    message_type VARCHAR(50) NOT NULL,
    text_content TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (telegram_user_id) REFERENCES bot_users(telegram_user_id)
);
```

### Таблица: user_sessions
```sql
CREATE TABLE user_sessions (
    id SERIAL PRIMARY KEY,
    telegram_user_id BIGINT NOT NULL,
    session_data JSONB DEFAULT '{}',
    last_command VARCHAR(255),
    context JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (telegram_user_id) REFERENCES bot_users(telegram_user_id)
);
```

### Таблица: api_logs
```sql
CREATE TABLE api_logs (
    id SERIAL PRIMARY KEY,
    service_name VARCHAR(100) NOT NULL,
    endpoint VARCHAR(500) NOT NULL,
    method VARCHAR(10) NOT NULL,
    request_data JSONB,
    response_status INTEGER,
    response_data JSONB,
    execution_time FLOAT,
    telegram_user_id BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 🏗️ Архитектура классов

### NetBox Service
```python
class NetBoxService:
    def __init__(self, base_url: str, token: str)
    async def get_devices(self, search: str = None, limit: int = 10)
    async def get_device_by_id(self, device_id: int)
    async def get_sites(self, search: str = None)
    async def get_site_by_id(self, site_id: int)
    async def search_ip_addresses(self, query: str)
    async def get_device_interfaces(self, device_id: int)
```

### Bot Handlers
```python
class SearchHandler:
    async def search_devices(message: Message, command: CommandObject)
    async def show_device_info(callback: CallbackQuery)
    async def show_site_info(callback: CallbackQuery)
    
class AdminHandler:
    async def show_users(message: Message)
    async def show_logs(message: Message)
    async def broadcast_message(message: Message)
    
class GroupMonitorHandler:
    async def log_group_message(message: Message)
    async def handle_group_command(message: Message)
```

## 🔧 Конфигурационные файлы

### requirements.txt
```
aiogram==3.7.0
asyncpg==0.29.0
aiohttp==3.9.5
python-dotenv==1.0.1
loguru==0.7.2
redis==5.0.4
sqlalchemy[asyncio]==2.0.30
alembic==1.13.1
pydantic==2.7.3
pydantic-settings==2.3.2
```

### .env шаблон
```bash
# Telegram Bot Configuration
TELEGRAM_TOKEN=7946588372:AAEfTtRuTshG7c9fiJn7gJqm66xDuFfcJS4
TELEGRAM_API_ID=26909576
TELEGRAM_API_HASH=93ee325250491fff0a64039c7d923179
ADMIN_USER_ID=28795547

# Database Configuration  
DATABASE_URL=postgresql+asyncpg://hhivp_user:HHivp2024$SecureDB#9x7mK@postgres:5432/hhivp_bot
REDIS_URL=redis://:Redis$Secure2024#HHivp8kL3@redis:6379/0

# API Integrations
NETBOX_URL=https://netbox.hhivp.com/api/
NETBOX_TOKEN=4644a00b4966c3a0cbd4354c0566c5bc50dcb818
VAULTWARDEN_URL=https://vault.hhivp.com
OUTLINE_URL=https://docs.hhivp.com

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
MAX_LOG_SIZE=100MB
LOG_RETENTION=30d
```

## 🔄 Workflow диаграммы

### Поиск устройств
```
Пользователь -> /search laptop
    ↓
Проверка прав доступа
    ↓
NetBox API запрос
    ↓ 
Форматирование результатов
    ↓
Inline клавиатура с результатами
    ↓
Callback обработчик -> Детальная информация
```

### Мониторинг групп
```
Сообщение в группе
    ↓
Middleware логирования
    ↓
Парсинг сообщения
    ↓
Сохранение в PostgreSQL
    ↓
Проверка на команды боту
    ↓
Обработка команды (если есть)
```

## 🚨 Обработка ошибок

### Иерархия исключений
```python
class BotException(Exception):
    """Базовое исключение бота"""
    
class APIException(BotException):
    """Ошибки внешних API"""
    
class AuthException(BotException):
    """Ошибки аутентификации"""
    
class DatabaseException(BotException):
    """Ошибки базы данных"""
    
class ValidationException(BotException):
    """Ошибки валидации данных"""
```

### Стратегии обработки
```python
ERROR_HANDLERS = {
    APIException: "🔌 Ошибка подключения к сервису. Попробуйте позже.",
    AuthException: "🔒 Недостаточно прав для выполнения операции.",
    DatabaseException: "💾 Ошибка базы данных. Администратор уведомлен.",
    ValidationException: "⚠️ Некорректные данные. Проверьте ввод.",
}
```

## 📊 Метрики и мониторинг

### Ключевые метрики
```python
METRICS = {
    'messages_processed': 'Количество обработанных сообщений',
    'api_requests': 'Количество API запросов',
    'response_time': 'Время ответа бота',
    'active_users': 'Активные пользователи',
    'error_rate': 'Частота ошибок',
    'command_usage': 'Статистика использования команд'
}
```

### Система алертов
```python
ALERTS = {
    'high_error_rate': 'Высокая частота ошибок (>5%)',
    'slow_response': 'Медленный ответ (>3 сек)',
    'api_down': 'Недоступность внешнего API',
    'database_issues': 'Проблемы с базой данных'
}
```

## 🧪 Тестирование

### Структура тестов
```
tests/
├── unit/
│   ├── test_services/
│   ├── test_handlers/
│   └── test_utils/
├── integration/
│   ├── test_api_clients/
│   └── test_database/
└── e2e/
    └── test_bot_scenarios/
```

### Тестовые данные
```python
TEST_DATA = {
    'test_user': {
        'telegram_user_id': 123456789,
        'username': 'testuser',
        'role': 'user'
    },
    'test_device': {
        'id': 999,
        'name': 'Test Device',
        'device_type': 'Test Type'
    }
}
```

## 🔐 Безопасность

### Валидация входных данных
```python
from pydantic import BaseModel, validator

class SearchQuery(BaseModel):
    query: str
    limit: int = 10
    
    @validator('query')
    def validate_query(cls, v):
        if len(v) < 2:
            raise ValueError('Query too short')
        return v.strip()
```

### Rate Limiting
```python
RATE_LIMITS = {
    'default': '10/minute',
    'search': '30/minute', 
    'admin': '100/minute'
}
```

## 📱 Интерфейс пользователя

### Inline клавиатуры
```python
def device_keyboard(devices: List[Device]) -> InlineKeyboardMarkup:
    keyboard = []
    for device in devices:
        keyboard.append([
            InlineKeyboardButton(
                text=f"🖥️ {device.name}",
                callback_data=f"device:{device.id}"
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
```

### Меню команд
```python
COMMANDS_MENU = [
    BotCommand("start", "🚀 Начать работу с ботом"),
    BotCommand("search", "🔍 Поиск устройств в NetBox"),
    BotCommand("sites", "🏢 Список сайтов"),
    BotCommand("vault", "🔐 Поиск в Vaultwarden"),
    BotCommand("docs", "📚 Поиск в документации"),
    BotCommand("help", "❓ Справка по командам"),
]
```

---

**Статус:** 📝 Техническая спецификация готова  
**Следующий шаг:** Создание базовой структуры проекта