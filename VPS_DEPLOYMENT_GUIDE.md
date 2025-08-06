# 🚀 VPS Deployment Guide - HHIVP IT Assistant Bot

## 🎯 Пошаговые инструкции по развертыванию

---

## 📋 Предварительные требования

### На VPS должно быть установлено:
- Ubuntu 20.04+ или CentOS 8+
- Docker 20.10+
- Docker Compose 2.0+
- Git
- Python 3.11+

---

## 🔧 Шаг 1: Подготовка VPS

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка необходимых пакетов
sudo apt install -y git curl wget python3 python3-pip python3-venv

# Установка Docker (если не установлен)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Установка Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Перелогинивание для применения группы docker
newgrp docker
```

---

## 📦 Шаг 2: Клонирование проекта

```bash
# Переход в директорию проектов
cd /opt

# Клонирование репозитория (замените на ваш URL)
sudo git clone https://github.com/YOUR_USERNAME/tg-mordern-bot.git
sudo chown -R $USER:$USER tg-mordern-bot
cd tg-mordern-bot

# Проверка файлов
ls -la
```

---

## ⚙️ Шаг 3: Настройка окружения

```bash
# Создание .env файла для продакшн
cp .env.example .env.prod

# Редактирование настроек продакшн
nano .env.prod
```

### 🔐 Настройки .env.prod:

```env
# Telegram Bot
TELEGRAM_TOKEN=ваш_реальный_токен_бота
TELEGRAM_API_ID=ваш_api_id
TELEGRAM_API_HASH=ваш_api_hash
ADMIN_USER_IDS=ваши_telegram_id_через_запятую

# Database (продакшн настройки)
DATABASE_URL=postgresql+asyncpg://bot_user:СИЛЬНЫЙ_ПАРОЛЬ@localhost:5432/telegram_bot_prod
REDIS_URL=redis://:СИЛЬНЫЙ_REDIS_ПАРОЛЬ@localhost:6379/0

# n8n Integration
N8N_WEBHOOK_URL=https://ваш-n8n.com/webhook/work-journal

# Group Notifications  
WORK_JOURNAL_GROUP_CHAT_ID=ваш_группой_чат_id
GOOGLE_SHEETS_URL=ссылка_на_вашу_таблицу

# Logging
LOG_LEVEL=INFO
```

---

## 🐳 Шаг 4: Создание продакшн Docker конфигурации

```bash
# Создание продакшн docker-compose файла
nano docker-compose.prod.yml
```

### docker-compose.prod.yml:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: telegram-bot-postgres-prod
    restart: unless-stopped
    environment:
      POSTGRES_DB: telegram_bot_prod
      POSTGRES_USER: bot_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data_prod:/var/lib/postgresql/data
      - ./sql:/docker-entrypoint-initdb.d
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U bot_user -d telegram_bot_prod"]
      interval: 30s
      timeout: 10s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: telegram-bot-redis-prod
    restart: unless-stopped
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data_prod:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 5

  bot:
    build: .
    container_name: telegram-bot-prod
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    env_file:
      - .env.prod
    volumes:
      - ./logs:/app/logs
      - ./backups:/app/backups
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8000/health', timeout=5)"]
      interval: 60s
      timeout: 10s
      retries: 3

volumes:
  postgres_data_prod:
  redis_data_prod:
```

---

## 🔧 Шаг 5: Создание скрипта развертывания

```bash
# Создание скрипта развертывания
nano deploy-prod.sh
chmod +x deploy-prod.sh
```

### deploy-prod.sh:

```bash
#!/bin/bash

echo "🚀 Deploying HHIVP IT Assistant Bot to Production"
echo "=================================================="

# Остановка существующих контейнеров
echo "🛑 Stopping existing containers..."
docker-compose -f docker-compose.prod.yml down

# Обновление кода
echo "📦 Updating code..."
git pull origin main

# Создание виртуального окружения
echo "🐍 Setting up Python environment..."
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Установка паролей
echo "🔐 Please set strong passwords:"
read -s -p "Enter PostgreSQL password: " DB_PASSWORD
echo
read -s -p "Enter Redis password: " REDIS_PASSWORD
echo

export DB_PASSWORD
export REDIS_PASSWORD

# Запуск сервисов
echo "🚀 Starting services..."
docker-compose -f docker-compose.prod.yml up -d

# Ожидание запуска БД
echo "⏳ Waiting for database to be ready..."
sleep 30

# Применение миграций
echo "🗄️ Running database migrations..."
source venv/bin/activate
alembic upgrade head

# Проверка статуса
echo "📊 Checking service status..."
docker-compose -f docker-compose.prod.yml ps

echo "✅ Deployment completed!"
echo "📋 Check logs: docker-compose -f docker-compose.prod.yml logs -f"
```

---

## 🎯 Шаг 6: Развертывание

```bash
# Запуск развертывания
./deploy-prod.sh
```

---

## 🔍 Шаг 7: Проверка и мониторинг

### Проверка статуса:
```bash
# Статус контейнеров
docker-compose -f docker-compose.prod.yml ps

# Логи бота
docker-compose -f docker-compose.prod.yml logs -f bot

# Логи базы данных
docker-compose -f docker-compose.prod.yml logs postgres

# Использование ресурсов
docker stats
```

### Тестирование:
```bash
# Тест основных компонентов
python test_basic.py

# Тест бота (в виртуальном окружении)
source venv/bin/activate
python test_work_journal.py
```

---

## 🔧 Шаг 8: Настройка автозапуска (systemd)

```bash
# Создание systemd сервиса
sudo nano /etc/systemd/system/hhivp-bot.service
```

### hhivp-bot.service:

```ini
[Unit]
Description=HHIVP IT Assistant Bot
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=true
WorkingDirectory=/opt/tg-mordern-bot
ExecStart=/usr/local/bin/docker-compose -f docker-compose.prod.yml up -d
ExecStop=/usr/local/bin/docker-compose -f docker-compose.prod.yml down
User=root

[Install]
WantedBy=multi-user.target
```

```bash
# Активация сервиса
sudo systemctl daemon-reload
sudo systemctl enable hhivp-bot.service
sudo systemctl start hhivp-bot.service

# Проверка статуса
sudo systemctl status hhivp-bot.service
```

---

## 📊 Шаг 9: Настройка мониторинга

### Создание скрипта мониторинга:

```bash
nano monitor.sh
chmod +x monitor.sh
```

```bash
#!/bin/bash

echo "📊 HHIVP Bot Monitoring Dashboard"
echo "=================================="

echo "🐳 Docker containers:"
docker-compose -f docker-compose.prod.yml ps

echo -e "\n💾 Disk usage:"
df -h

echo -e "\n🧠 Memory usage:"
free -h

echo -e "\n📈 System load:"
uptime

echo -e "\n🔍 Recent bot logs (last 10 lines):"
docker-compose -f docker-compose.prod.yml logs --tail=10 bot
```

---

## 🔄 Шаг 10: Обновления и обслуживание

### Скрипт обновления:

```bash
nano update.sh
chmod +x update.sh
```

```bash
#!/bin/bash

echo "🔄 Updating HHIVP IT Assistant Bot"
echo "=================================="

# Бэкап БД
echo "💾 Creating database backup..."
docker-compose -f docker-compose.prod.yml exec postgres pg_dump -U bot_user telegram_bot_prod > "backups/backup_$(date +%Y%m%d_%H%M%S).sql"

# Обновление кода
echo "📦 Updating code..."
git pull origin main

# Перезапуск сервисов
echo "🔄 Restarting services..."
docker-compose -f docker-compose.prod.yml restart

echo "✅ Update completed!"
```

---

## ⚠️ Важные команды для управления

```bash
# Запуск
docker-compose -f docker-compose.prod.yml up -d

# Остановка
docker-compose -f docker-compose.prod.yml down

# Перезапуск
docker-compose -f docker-compose.prod.yml restart

# Логи в реальном времени
docker-compose -f docker-compose.prod.yml logs -f

# Вход в контейнер бота
docker-compose -f docker-compose.prod.yml exec bot bash

# Бэкап БД
docker-compose -f docker-compose.prod.yml exec postgres pg_dump -U bot_user telegram_bot_prod > backup.sql

# Восстановление БД
docker-compose -f docker-compose.prod.yml exec -T postgres psql -U bot_user telegram_bot_prod < backup.sql
```

---

## 🛡️ Безопасность

### Настройка firewall:
```bash
# Установка ufw
sudo apt install ufw

# Основные правила
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Активация
sudo ufw enable
```

### SSL сертификат (если нужен веб-интерфейс):
```bash
# Установка certbot
sudo apt install certbot

# Получение сертификата
sudo certbot certonly --standalone -d your-domain.com
```

---

## 🆘 Устранение неполадок

### Проблемы с запуском:
```bash
# Проверка логов
docker-compose -f docker-compose.prod.yml logs

# Проверка конфигурации
docker-compose -f docker-compose.prod.yml config

# Пересборка контейнеров
docker-compose -f docker-compose.prod.yml build --no-cache
```

### Проблемы с БД:
```bash
# Проверка подключения к БД
docker-compose -f docker-compose.prod.yml exec postgres psql -U bot_user -d telegram_bot_prod -c "SELECT 1;"

# Проверка миграций
source venv/bin/activate && alembic current
```

---

## ✅ Проверочный чеклист

- [ ] VPS подготовлен (Docker, Git установлены)
- [ ] Репозиторий склонирован
- [ ] .env.prod настроен с правильными токенами
- [ ] Пароли БД установлены
- [ ] docker-compose.prod.yml создан
- [ ] Развертывание выполнено (`./deploy-prod.sh`)
- [ ] Контейнеры запущены и здоровы
- [ ] Миграции применены
- [ ] Бот отвечает на `/start`
- [ ] Журнал работ функционирует
- [ ] Systemd сервис настроен
- [ ] Мониторинг работает

---

## 🏆 Результат

После выполнения всех шагов у вас будет:

✅ **Полностью работающий бот на VPS**  
✅ **Автоматический запуск при перезагрузке**  
✅ **Система мониторинга и логирования**  
✅ **Бэкапы базы данных**  
✅ **Простые команды для обслуживания**

**Бот готов к продакшн использованию!** 🚀

---

*📅 Создано: 6 августа 2025*  
*👨‍💻 Версия: Production Ready*  
*🔧 Статус: Готово к развертыванию*
