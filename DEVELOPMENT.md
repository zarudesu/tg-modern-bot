# 🚀 Независимая разработка Telegram бота

Этот проект настроен для **независимой разработки** с использованием микросервисной архитектуры.

## 🏗️ Архитектура

```
📦 Telegram Bot Project
├── 🤖 Bot Application (локально или в Docker)
├── 🗄️ PostgreSQL Database (отдельный контейнер) 
├── 🔄 Redis Cache (отдельный контейнер)
└── 🌐 pgAdmin (опциональный веб-интерфейс)
```

## 🎯 Преимущества независимой разработки

✅ **Быстрый цикл разработки** - изменения бота применяются мгновенно  
✅ **Изолированная база данных** - можно тестировать с реальными данными  
✅ **Гибкость конфигурации** - разные настройки для разработки и продакшена  
✅ **Легкое тестирование** - каждый компонент можно тестировать отдельно  
✅ **Масштабируемость** - готовность к микросервисной архитектуре  

## 🚀 Быстрый старт

### 1. Настройка окружения
```bash
# Автоматическая настройка
./setup-dev.sh

# Или ручная настройка
make install
```

### 2. Настройка токенов
```bash
# Скопируйте и отредактируйте конфигурацию
cp .env.example .env
nano .env

# Добавьте:
# TELEGRAM_TOKEN=ваш_токен_от_BotFather
# ADMIN_USER_ID=ваш_telegram_id
```

### 3. Запуск разработки
```bash
# Запустить БД и бота одной командой
make dev

# Или пошагово:
make db-up     # Запустить базу данных
make bot-dev   # Запустить бота в режиме разработки
```

## 📋 Команды разработки

### 🗄️ База данных
```bash
make db-up      # Запустить PostgreSQL + Redis
make db-down    # Остановить базу данных
make db-logs    # Посмотреть логи БД
make db-shell   # Войти в PostgreSQL консоль
make db-admin   # Запустить pgAdmin (http://localhost:8080)
make db-backup  # Создать бэкап
```

### 🤖 Telegram бот
```bash
make bot-dev    # Запуск в режиме разработки (локально)
make bot-up     # Запуск в Docker
make bot-down   # Остановить бота
make bot-logs   # Посмотреть логи бота
```

### 🚀 Полный стек
```bash
make full-up    # Запустить всё в Docker
make full-down  # Остановить всё
make status     # Статус всех контейнеров
```

## 🔧 Режимы разработки

### 1. **Гибридный режим (рекомендуется)**
- **База данных**: в Docker контейнерах
- **Бот**: запущен локально в Python

```bash
make dev        # БД в Docker, бот локально
```

**Преимущества:**
- Мгновенное применение изменений
- Полноценная отладка в IDE
- Быстрый цикл разработки

### 2. **Полный Docker режим**
- **Всё**: в Docker контейнерах

```bash
make full-up    # Всё в Docker
```

**Преимущества:**
- Идентично продакшену
- Легко передать другим разработчикам

### 3. **Независимый режим**
- **БД**: отдельные контейнеры
- **Бот**: отдельный контейнер

```bash
make db-up      # Запустить БД
make bot-up     # Запустить бота отдельно
```

**Преимущества:**
- Полная изоляция компонентов
- Готовность к микросервисам

## 🌐 Подключения и порты

| Сервис | Локальный порт | Внутренний порт | Credentials |
|--------|----------------|-----------------|-------------|
| PostgreSQL | `5432` | `5432` | `bot_user:bot_password_2024` |
| Redis | `6379` | `6379` | `redis_password_2024` |
| pgAdmin | `8080` | `80` | `admin@example.com:admin_password_2024` |

## 📊 Мониторинг и отладка

### Логи
```bash
make db-logs    # Логи базы данных
make bot-logs   # Логи Telegram бота
make full-logs  # Все логи
```

### Веб-интерфейсы
```bash
make db-admin   # pgAdmin: http://localhost:8080
```

### Прямое подключение к БД
```bash
# Через make
make db-shell

# Напрямую
psql -h localhost -p 5432 -U bot_user -d telegram_bot
```

## 🔄 Workflow разработки

### Ежедневная разработка
```bash
# Утром
make dev                    # Запустить разработку

# В процессе разработки
# Редактируете код бота локально
# Изменения применяются мгновенно

# Тестирование
make test                   # Запустить тесты

# Вечером
make dev-stop               # Остановить разработку
```

### Тестирование изменений
```bash
# Локальное тестирование
make test                   # Базовые тесты

# Тестирование в Docker
make bot-down && make bot-up

# Полное тестирование
make full-down && make full-up
```

### Работа с базой данных
```bash
# Создание бэкапа перед экспериментами
make db-backup

# Восстановление при необходимости
make db-restore BACKUP_FILE=backups/backup_20240730_120000.sql.gz

# Просмотр данных в pgAdmin
make db-admin
# Переходите на http://localhost:8080
```

## 🔒 Конфигурация

### Файлы конфигурации
- `.env` - основная конфигурация
- `.env.dev` - настройки для разработки
- `.env.example` - пример конфигурации

### Переменные для разработки
```bash
# В .env.dev
DATABASE_URL=postgresql+asyncpg://bot_user:bot_password_2024@localhost:5432/telegram_bot
REDIS_URL=redis://:redis_password_2024@localhost:6379/0
LOG_LEVEL=DEBUG
ENABLE_DEBUG_COMMANDS=true
```

## 🚢 Деплой в продакшн

После разработки легко перейти к продакшену:

```bash
# Сборка для продакшена
docker build -t telegram-bot:latest .

# Или полный стек
make full-up
```

## 🛠️ Расширение и модули

Структура готова для добавления новых модулей:

```python
# app/handlers/new_module.py
from aiogram import Router

router = Router()

@router.message(Command("new_command"))
async def new_handler(message: Message):
    await message.answer("Новый модуль!")
```

```python
# app/main.py
from .handlers import start, new_module

dp.include_router(new_module.router)
```

## 📞 Поддержка

**Проблемы с Docker:**
```bash
make status     # Проверить статус
docker ps       # Все контейнеры
docker logs <container_name>
```

**Проблемы с подключением к БД:**
```bash
make db-shell   # Проверить подключение
```

**Полная переустановка:**
```bash
make full-clean  # Удалить всё и начать заново
./setup-dev.sh   # Переустановить
```

---

🎉 **Готово к независимой разработке!**
