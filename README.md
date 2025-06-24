# 🏢 HHIVP IT-Outsource Management System

> Централизованная система управления IT-аутсорсингом для команды разработчиков

[![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)](https://www.docker.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue?logo=postgresql)](https://www.postgresql.org/)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-blue?logo=telegram)](https://core.telegram.org/bots)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 🎯 Описание проекта

Полнофункциональная система для управления IT-аутсорсинговой деятельностью с возможностями:

- 🌐 **NetBox** - документирование клиентских сетей и устройств
- 🔐 **Vaultwarden** - безопасное хранение паролей и доступов  
- 📚 **BookStack** - централизованная база знаний
- 🤖 **Telegram-бот** - быстрый поиск по всем системам
- 🔄 **Автоматизация** - backup, мониторинг, уведомления

## 📊 Характеристики

| Параметр | Значение |
|----------|----------|
| **Команда** | 3 разработчика |
| **Клиенты** | 5-6 юридических лиц |
| **Инфраструктура** | ~300 компьютеров, 20-30 серверов |
| **Отрасли** | 3D-печать, медицина, строительство, туризм |

## 🚀 Быстрый старт

```bash
# 1. Клонирование проекта
git clone <repository-url> hhivp-it-system
cd hhivp-it-system

# 2. Настройка окружения
cp .env.example .env
# Отредактируйте .env с вашими настройками

# 3. Автоматическое развертывание
chmod +x scripts/deploy.sh
./scripts/deploy.sh

# 4. Настройка SSL и доменов (см. документацию)
```

**📋 Подробная инструкция:** [docs/DEPLOYMENT_CHECKLIST.md](docs/DEPLOYMENT_CHECKLIST.md)

## 🏗️ Архитектура

### Этап 1: Основные компоненты ✅
- [x] NetBox (документирование инфраструктуры)
- [x] Vaultwarden (менеджер паролей)
- [x] BookStack (база знаний)
- [x] Telegram-бот (универсальный поиск)
- [x] PostgreSQL + Redis (данные и кеширование)
- [x] Nginx Proxy Manager (SSL и домены)

### Этап 2: Развитие 🔄
- [ ] Система обращений клиентов
- [ ] LLM интеграция (Ollama)
- [ ] Расширенная аналитика

### Этап 3: Будущее 🚀
- [ ] Миграция на Siyuan
- [ ] Умный чат-бот для клиентов
- [ ] Интеграция с Контур.Эльба

## 🌐 Доступные сервисы

| Сервис | URL | Описание |
|--------|-----|----------|
| **NetBox** | https://netbox.hhivp.com | Документирование сетей |
| **Vaultwarden** | https://vault.hhivp.com | Менеджер паролей |
| **BookStack** | https://docs.hhivp.com | База знаний |
| **Nginx Proxy** | http://server:81 | Управление SSL |
| **Telegram Bot** | @hhivp_it_bot | Поиск и управление |

## 🤖 Команды Telegram-бота

```
🔍 Поиск:
/search <запрос>     - универсальный поиск
/ip <адрес>          - информация об IP
/device <название>   - поиск устройства  
/client <название>   - информация о клиенте
/password <сервис>   - поиск пароля

📊 Статус:
/status              - статус всех систем
/help                - справка по командам

👑 Администрирование:
/admin               - панель администратора
/stats               - статистика использования
/backup              - создать резервную копию
/logs                - просмотр логов
```

## 🛠️ Управление системой

```bash
# Статус всех сервисов
docker-compose -f docker-compose.simple.yml ps

# Логи конкретного сервиса
docker-compose -f docker-compose.simple.yml logs -f telegram-bot

# Перезапуск сервиса
docker-compose -f docker-compose.simple.yml restart netbox

# Резервное копирование
./scripts/backup.sh

# Обновление системы
git pull
docker-compose -f docker-compose.simple.yml pull
docker-compose -f docker-compose.simple.yml up -d --build
```

## 📁 Структура проекта

```
hhivp-it-system/
├── docker/              # Docker конфигурации
├── telegram-bot/        # Код Telegram-бота
│   ├── handlers/        # Обработчики команд
│   ├── services/        # Клиенты внешних API
│   └── database.py      # Работа с БД
├── custom-services/     # Собственные разработки
├── configs/             # Конфигурационные файлы
├── scripts/             # Скрипты автоматизации
├── docs/                # Документация
├── backup/              # Резервные копии
├── docker-compose.*.yml # Docker Compose файлы
└── .env                 # Переменные окружения
```

## 🔒 Безопасность

- 🔐 **Шифрование**: Все пароли в Vaultwarden зашифрованы
- 🌐 **SSL**: Let's Encrypt сертификаты для всех доменов
- 📝 **Аудит**: Логирование всех действий пользователей
- 🚫 **Доступ**: Ограниченный список пользователей бота
- 💾 **Backup**: Ежедневное резервное копирование

## 📊 Мониторинг

- **Логи системы**: `/opt/hhivp-it-system/logs/`
- **Резервные копии**: `/opt/hhivp-it-system/backup/`
- **Статус сервисов**: через Telegram-бот `/status`
- **Метрики**: встроенная аналитика использования

## 🤝 Поддержка

При возникновении проблем:

1. **Проверьте статус**: `docker-compose -f docker-compose.simple.yml ps`
2. **Просмотрите логи**: `docker-compose -f docker-compose.simple.yml logs [service]`
3. **Проверьте конфигурацию**: настройки в `.env` файле
4. **DNS и SSL**: корректность доменов и сертификатов

## 📚 Документация

- [📋 Чек-лист развертывания](docs/DEPLOYMENT_CHECKLIST.md)
- [🚀 Быстрый старт](docs/QUICKSTART.md)
- [🔧 Руководство по развертыванию](docs/DEPLOYMENT.md)

## 📈 Статистика проекта

- **Языки**: Python, YAML, Shell
- **Контейнеры**: 6 основных сервисов
- **Базы данных**: 5 отдельных БД
- **API интеграции**: NetBox, BookStack, Telegram
- **Автоматизация**: 100% развертывание через скрипты

---

**🎉 Система готова к продуктивному использованию командой HHIVP!**

*Разработано для централизации управления IT-инфраструктурой и повышения эффективности команды.*
