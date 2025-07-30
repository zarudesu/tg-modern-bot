# 📖 TELEGRAM BOT DOCUMENTATION - HHIVP IT SYSTEM

## 🎯 Общая информация

**Название проекта:** HHIVP IT Management Bot  
**Версия:** 1.0.0  
**Дата создания:** 28 июня 2025  
**Автор:** @zardes  

## 📋 Цель проекта

Создание многофункционального Telegram бота для управления IT-инфраструктурой HHIVP с интеграцией NetBox, Vaultwarden, Outline, Zammad и мониторингом групповых сообщений.

## 🏗️ Архитектура системы

### Технический стек
- **Python 3.13+**
- **aiogram 3.x** (async Telegram Bot framework)
- **PostgreSQL** (логи, пользователи, сессии)
- **Redis** (кэш, сессии)
- **Docker & Docker Compose**
- **aiohttp** (HTTP клиент для API)

### Структура проекта
```
telegram-bot/
├── app/
│   ├── __init__.py
│   ├── main.py                 # Точка входа
│   ├── config.py              # Конфигурация
│   ├── database/
│   │   ├── __init__.py
│   │   ├── models.py          # SQLAlchemy модели
│   │   ├── database.py        # Подключение к БД
│   │   └── migrations/        # Alembic миграции
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── start.py           # /start команда
│   │   ├── search.py          # Поиск в NetBox
│   │   ├── vault.py           # Работа с Vaultwarden
│   │   ├── admin.py           # Административные команды
│   │   └── groups.py          # Мониторинг групп
│   ├── services/
│   │   ├── __init__.py
│   │   ├── netbox_service.py  # NetBox API клиент
│   │   ├── vault_service.py   # Vaultwarden API
│   │   ├── outline_service.py # Outline API
│   │   ├── zammad_service.py  # Zammad API
│   │   └── auth_service.py    # Аутентификация
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── auth.py            # Проверка прав доступа
│   │   ├── logging.py         # Логирование
│   │   └── throttling.py      # Rate limiting
│   └── utils/
│       ├── __init__.py
│       ├── logger.py          # Настройка логирования
│       ├── formatters.py      # Форматирование сообщений
│       └── helpers.py         # Вспомогательные функции
├── docker/
│   ├── Dockerfile
│   └── requirements.txt
├── docker-compose.yml
├── .env
└── README.md
```

## 🔑 Интеграции

### NetBox API
- **URL:** `https://netbox.hhivp.com/api/`
- **Token:** `4644a00b4966c3a0cbd4354c0566c5bc50dcb818`
- **Функции:**
  - Поиск устройств по имени/типу/сайту
  - Просмотр информации об устройствах
  - Список сайтов и локаций
  - IP адреса и сети
  - Кабельные подключения

### Vaultwarden API
- **URL:** `https://vault.hhivp.com`
- **Функции:**
  - Поиск записей в базе знаний
  - Получение secure notes
  - Просмотр организационных данных

### Outline API  
- **URL:** `https://docs.hhivp.com`
- **Функции:**
  - Поиск в документации
  - Просмотр коллекций документов

### Zammad API
- **Функции:**
  - Список тикетов
  - Создание новых тикетов
  - Обновление статуса тикетов

### PostgreSQL
- **База:** `hhivp_user:HHivp2024$SecureDB#9x7mK`
- **Таблицы:**
  - `bot_users` - пользователи бота
  - `message_logs` - логи сообщений
  - `user_sessions` - сессии пользователей
  - `access_roles` - роли доступа

## 👥 Система ролей

### Администратор (@zardes)
- Полный доступ ко всем функциям
- Управление пользователями
- Просмотр логов
- Административные команды

### Пользователь
- Поиск в NetBox (только чтение)
- Поиск в Vaultwarden
- Просмотр документации Outline
- Создание тикетов в Zammad

### Гость
- Базовый поиск в NetBox
- Ограниченный доступ к функциям

## 🤖 Команды бота

### Основные команды
```
/start - Регистрация и приветствие
/help - Справка по командам
/profile - Информация о профиле
/settings - Настройки пользователя
```

### NetBox команды
```
/search <query> - Поиск устройств в NetBox
/device <id> - Детальная информация об устройстве
/sites - Список всех сайтов
/site <id> - Информация о сайте
/ip <address> - Информация об IP адресе
```

### Интеграции
```
/vault <query> - Поиск в Vaultwarden
/docs <query> - Поиск в Outline документации
/tickets - Мои тикеты в Zammad
/ticket <id> - Информация о тикете
/newticket - Создать новый тикет
```

### Административные команды
```
/users - Список пользователей (только админ)
/logs - Просмотр логов (только админ)
/stats - Статистика использования (только админ)
/broadcast - Рассылка сообщений (только админ)
```

## 🔍 Мониторинг групп

### Функциональность
- Автоматическое логирование всех сообщений в группах
- Сохранение в PostgreSQL с метаданными
- Поиск по логам групповых сообщений
- Статистика активности участников

### Логируемые данные
- ID сообщения и пользователя
- Текст сообщения
- Время отправки
- Тип сообщения (текст/фото/документ)
- Метаданные группы

## 🛡️ Безопасность

### Аутентификация
- Проверка Telegram User ID
- Система ролей с проверкой прав
- Rate limiting для API запросов
- Валидация входящих данных

### Логирование
- Все действия пользователей
- API запросы и ответы
- Ошибки и исключения
- Система ротации логов

## 🚀 Docker конфигурация

### Dockerfile
```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app/ ./app/
CMD ["python", "app/main.py"]
```

### Docker Compose
```yaml
version: '3.8'
services:
  hhivp-bot:
    build: ./telegram-bot
    environment:
      - TELEGRAM_TOKEN=${TELEGRAM_TOKEN}
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
```

## 📊 Мониторинг и метрики

### Логи
- Структурированное JSON логирование
- Уровни: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Ротация логов по размеру и времени

### Метрики
- Количество обработанных сообщений
- Время ответа API запросов
- Статистика использования команд
- Активность пользователей

## 🔧 Конфигурация

### Переменные окружения
```bash
# Telegram
TELEGRAM_TOKEN=7946588372:AAEfTtRuTshG7c9fiJn7gJqm66xDuFfcJS4
TELEGRAM_API_ID=26909576
TELEGRAM_API_HASH=93ee325250491fff0a64039c7d923179

# База данных
DATABASE_URL=postgresql://hhivp_user:HHivp2024$SecureDB#9x7mK@postgres:5432/hhivp_bot
REDIS_URL=redis://:Redis$Secure2024#HHivp8kL3@redis:6379/0

# Интеграции
NETBOX_URL=https://netbox.hhivp.com/api/
NETBOX_TOKEN=4644a00b4966c3a0cbd4354c0566c5bc50dcb818
VAULTWARDEN_URL=https://vault.hhivp.com
OUTLINE_URL=https://docs.hhivp.com

# Администратор
ADMIN_USER_ID=28795547
```

## 📝 Планы развития

### Версия 1.1
- Веб-интерфейс для администрирования
- Дополнительные команды для NetBox
- Интеграция с мониторингом

### Версия 1.2
- Автоматические уведомления о событиях
- Расширенная система ролей
- API для внешних интеграций

### Версия 2.0
- Машинное обучение для анализа логов
- Предиктивная аналитика
- Расширенная отчетность

---

## 🚦 Статус проекта

- [x] Предварительная документация
- [ ] Базовая структура проекта
- [ ] Настройка базы данных
- [ ] Основные команды бота
- [ ] Интеграция с NetBox
- [ ] Интеграция с Vaultwarden
- [ ] Система ролей
- [ ] Мониторинг групп
- [ ] Docker конфигурация
- [ ] Тестирование
- [ ] Деплой на VPS

**Дата обновления:** 28 июня 2025