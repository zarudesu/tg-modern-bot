# 🐳 Развертывание

## Docker (рекомендуемый)

### Разработка:
```bash
# Запуск
make dev

# Перезапуск
make dev-restart

# Остановка
make dev-stop
```

### Производство:
```bash
# Первый запуск
docker-compose -f docker-compose.prod.yml up -d

# Обновление
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d
```

## VPS развертывание

### 1. Подготовка сервера:
```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
sudo usermod -aG docker $USER

# Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 2. Настройка проекта:
```bash
# Клонирование
git clone <repository-url>
cd tg-mordern-bot

# Конфигурация
cp .env.example .env
nano .env  # Заполнить переменные
```

### 3. Системный сервис:
```bash
# Установка сервиса
sudo cp hhivp-it-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable hhivp-it-bot
sudo systemctl start hhivp-it-bot

# Проверка статуса
sudo systemctl status hhivp-it-bot
```

## Переменные окружения

### Обязательные:
```env
TELEGRAM_TOKEN=bot_token
ADMIN_USER_ID=your_telegram_id
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
```

### Опциональные:
```env
# Redis
REDIS_URL=redis://localhost:6379

# Plane интеграция
PLANE_API_URL=https://plane-instance.com
PLANE_API_TOKEN=plane_token
PLANE_WORKSPACE_SLUG=workspace

# n8n webhook
N8N_WEBHOOK_URL=https://n8n-instance.com/webhook/work-journal

# Логирование
LOG_LEVEL=INFO
LOG_FORMAT=json

# Безопасность
RATE_LIMIT_DEFAULT=10/minute
```

## Мониторинг

### Логи:
```bash
# Бот
docker logs telegram-bot-app -f

# База данных
docker logs telegram-bot-postgres -f

# Все сервисы
docker-compose logs -f
```

### Здоровье системы:
```bash
# Статус контейнеров
docker ps

# Использование ресурсов
docker stats

# Проверка подключений
make db-shell
```

### Метрики:
- CPU/Memory через `docker stats`
- Логи ошибок в файлах `logs/`
- Telegram API rate limits в логах

## Обновление

### Обновление кода:
```bash
git pull origin main
docker-compose build --no-cache
docker-compose up -d
```

### Миграции БД:
```bash
# Проверить новые миграции
docker exec telegram-bot-app alembic current
docker exec telegram-bot-app alembic heads

# Применить
docker exec telegram-bot-app alembic upgrade head
```

### Откат:
```bash
# Откат кода
git checkout previous_commit
docker-compose build --no-cache
docker-compose up -d

# Откат БД
docker exec telegram-bot-app alembic downgrade -1
```

## Резервное копирование

### База данных:
```bash
# Создание backup
make db-backup

# Ручное создание
docker exec telegram-bot-postgres pg_dump -U postgres telegram_bot > backup.sql

# Восстановление
docker exec -i telegram-bot-postgres psql -U postgres telegram_bot < backup.sql
```

### Конфигурация:
```bash
# Backup конфигов
tar -czf config-backup.tar.gz .env docker-compose.yml
```

## Безопасность

### Firewall:
```bash
# Закрыть ненужные порты
sudo ufw enable
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443
```

### SSL/HTTPS:
```bash
# Certbot для Let's Encrypt
sudo apt install certbot
sudo certbot certonly --standalone -d yourdomain.com
```

### Секреты:
- Никогда не коммитить `.env`
- Использовать `docker secrets` в продакшене
- Регулярно ротировать токены

## Траблшутинг

### Бот не отвечает:
```bash
# Проверить статус
docker ps
make status

# Логи
make bot-logs

# Перезапуск
make dev-restart
```

### БД недоступна:
```bash
# Проверить подключение
make db-shell

# Перезапуск БД
docker-compose restart postgres

# Проверить логи
docker logs telegram-bot-postgres
```

### Высокое потребление ресурсов:
```bash
# Мониторинг
docker stats

# Профилирование
# (встроено в PerformanceMiddleware)

# Очистка логов
docker system prune -f
```

### Ошибки миграций:
```bash
# Проверить статус
docker exec telegram-bot-app alembic current

# Ручное исправление
docker exec -it telegram-bot-app bash
alembic stamp head  # При крайней необходимости
```

## Масштабирование

### Горизонтальное:
- Использовать Redis для сессий
- Load balancer для webhook
- Несколько инстансов бота

### Вертикальное:
```yaml
# docker-compose.yml
services:
  telegram-bot:
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '0.5'
```

### Оптимизация:
- Включить Redis кеширование
- Настроить пулы соединений БД
- Использовать CDN для статики
