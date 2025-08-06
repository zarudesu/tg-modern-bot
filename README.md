# 🤖 Modern Telegram Bot - Production Ready

[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.11+-green.svg)](https://python.org/)
[![Telegram](https://img.shields.io/badge/Telegram-Bot%20API-blue.svg)](https://core.telegram.org/bots/api)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue.svg)](https://postgresql.org/)

**Современный Telegram-бот для управления IT-командой с полной интеграцией в production окружение.**

---

## ✨ **Ключевые возможности**

### 📊 **Журнал работ**
- ✅ Создание записей о выполненных работах
- ✅ Множественный выбор исполнителей
- ✅ Парсинг времени: "1 час 30 минут" → 90 минут
- ✅ Фильтрация по дате, компании, работнику
- ✅ Экспорт отчетов

### 🔗 **Интеграции**
- ✅ **n8n** - автоматическая отправка в Google Sheets
- ✅ **Telegram Groups** - уведомления с упоминаниями
- ✅ **PostgreSQL** - надежное хранение данных
- ✅ **Redis** - кэширование и сессии

### 🐳 **Production Ready**
- ✅ **Docker** контейнеризация
- ✅ **Alembic** миграции БД
- ✅ **Makefile** команды развертывания
- ✅ **Health checks** и мониторинг
- ✅ **Graceful shutdown**

---

## 🚀 **Быстрый старт**

### 1️⃣ **Клонирование и настройка**
```bash
# Клонировать репозиторий
git clone https://github.com/zarudesu/tg-modern-bot.git
cd tg-modern-bot

# Создать конфигурацию из шаблона
cp .env.example .env
```

### 2️⃣ **Получить токены**
1. **Telegram Bot**: Создать в [@BotFather](https://t.me/BotFather)
2. **API Credentials**: Получить на [my.telegram.org](https://my.telegram.org)
3. **Admin ID**: Узнать через [@userinfobot](https://t.me/userinfobot)

### 3️⃣ **Заполнить .env файл**
```env
TELEGRAM_TOKEN=ваш_токен_от_botfather
TELEGRAM_API_ID=ваш_api_id
TELEGRAM_API_HASH=ваш_api_hash
ADMIN_USER_IDS=ваш_telegram_id
```

### 4️⃣ **Запустить**
```bash
# Режим разработки (база в Docker, бот локально)
make dev

# Полный stack в Docker
make full-up

# Production развертывание
make prod-deploy
```

---

## 📁 **Архитектура проекта**

```
tg-modern-bot/
├── 📁 app/                    # Основной код приложения
│   ├── 📁 handlers/          # Telegram обработчики
│   ├── 📁 services/          # Бизнес-логика
│   ├── 📁 database/          # Модели и БД
│   ├── 📁 middleware/        # Промежуточное ПО
│   └── 📁 integrations/      # Внешние API
├── 📁 docs/                  # Полная документация
├── 📁 alembic/              # Миграции БД
├── 🐳 docker-compose.yml    # Docker конфигурация
├── ⚡ Makefile              # Команды развертывания
└── 🔧 .env.example         # Шаблон конфигурации
```

---

## 🛠️ **Команды разработки**

### **Разработка**
```bash
make dev          # База в Docker, бот локально
make dev-restart  # Перезапуск разработки
make dev-stop     # Остановка
```

### **База данных**
```bash
make db-up        # Запустить PostgreSQL + Redis
make db-shell     # PostgreSQL консоль  
make db-admin     # pgAdmin веб-интерфейс
make db-backup    # Создать бэкап
```

### **Production**
```bash
make prod-deploy  # Полное развертывание
make prod-up      # Запуск сервисов
make prod-logs    # Просмотр логов
make prod-backup  # Бэкап продакшена
```

### **Тестирование**
```bash
make test                    # Запуск всех тестов
python test_work_journal.py  # Тест журнала работ
python test_n8n_integration.py  # Тест n8n
```

---

## 🔐 **Безопасность**

### ✅ **Безопасная конфигурация**
- 🔒 Токены только в `.env` файлах (не в Git)
- 🔒 Авторизация по `ADMIN_USER_IDS`
- 🔒 Валидация всех данных через Pydantic
- 🔒 SQL Injection защита через SQLAlchemy ORM

### ✅ **Production готовность**  
- 🔒 Environment variables для всех секретов
- 🔒 Docker secrets поддержка
- 🔒 Rate limiting настроен
- 🔒 Полное логирование действий

---

## 📊 **Модули системы**

### 🎯 **Журнал работ** *(v1.1 - Готов)*
- Создание записей через удобный интерфейс
- Множественный выбор исполнителей  
- Умный парсер времени работы
- Фильтрация и поиск записей
- Экспорт в различных форматах

### 🔗 **n8n интеграция** *(v1.1 - Готов)*
- Автоматическая отправка в Google Sheets
- Webhook с retry механизмом
- Структурированные данные в JSON
- Логирование всех операций

### 📢 **Система упоминаний** *(v1.1 - Готов)*
- Упоминания работников в Telegram
- Интеграция с Plane для задач  
- Групповые уведомления
- Гибкие настройки уведомлений

---

## 📚 **Документация**

### 📖 **Основная документация**
- [**Быстрый старт**](docs/QUICK_START.md) - Первые шаги
- [**Руководство разработчика**](docs/DEVELOPMENT_GUIDE.md) - Детальное руководство
- [**Production развертывание**](PRODUCTION_DEPLOYMENT.md) - Настройка продакшена
- [**Архитектура**](ARCHITECTURE.md) - Техническая архитектура

### 🔧 **Интеграции**
- [**n8n + Google Sheets**](docs/N8N_GOOGLE_SHEETS_INTEGRATION_GUIDE.md)
- [**Plane интеграция**](docs/PLANE_INTEGRATION_WITH_MENTIONS.md)  
- [**Система упоминаний**](docs/WORKER_MENTIONS_SYSTEM.md)

### 🔐 **Безопасность**
- [**Уведомление о безопасности**](SECURITY_NOTICE.md) - Важная информация
- [**Политика безопасности**](SECURITY.md) - Рекомендации

---

## 🛡️ **Требования**

### **Минимальные требования:**
- 🐧 **OS**: Linux/macOS/Windows + Docker
- 🐍 **Python**: 3.11+
- 🐳 **Docker**: 20.10+
- 💾 **RAM**: 512MB+ 
- 💿 **Storage**: 1GB+

### **Production требования:**
- 🖥️ **VPS**: 1 vCPU, 1GB RAM, 10GB SSD
- 🌐 **Домен**: Для webhook'ов (опционально)
- 🔐 **SSL**: Let's Encrypt автоматически
- 📊 **Мониторинг**: Встроенные health checks

---

## 🤝 **Участие в разработке**

### **Вклад приветствуется!**
1. 🍴 Fork репозиторий
2. 🌟 Создать feature branch
3. 🔧 Внести изменения
4. ✅ Добавить тесты
5. 📝 Обновить документацию
6. 🚀 Создать Pull Request

### **Сообщить о проблеме:**
- 🐛 [Issues](https://github.com/zarudesu/tg-modern-bot/issues) - Баги и предложения
- 💬 [Discussions](https://github.com/zarudesu/tg-modern-bot/discussions) - Вопросы и идеи

---

## 📜 **Лицензия**

Этот проект распространяется под лицензией **MIT License**.  
Подробности в файле [LICENSE](LICENSE).

---

## 🏆 **Статус проекта**

**✅ Production Ready v2.0** - Готов к использованию в продакшене!

### **🎯 Roadmap v2.1:**
- [ ] REST API для внешних интеграций
- [ ] Веб-интерфейс администрирования  
- [ ] Расширенная система ролей
- [ ] Интеграция с NetBox
- [ ] Slack/Discord поддержка

---

**🚀 Готов к использованию! Развертывайте и автоматизируйте свою IT-команду!**

---

*📅 Последнее обновление: Август 2025*  
*⭐ Поставьте звезду, если проект полезен!*
