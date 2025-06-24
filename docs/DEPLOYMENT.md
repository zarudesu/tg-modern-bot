# Руководство по развертыванию IT-Outsource System

## Предварительные требования

### На сервере должно быть установлено:
- Docker (версия 20.10+)
- Docker Compose (версия 2.0+)
- Git
- Nginx (опционально, для SSL)

### Домены должны указывать на сервер:
- netbox.hhivp.com
- vault.hhivp.com  
- docs.hhivp.com

## Процесс развертывания

### 1. Клонирование проекта
```bash
cd /opt
git clone <repository_url> hhivp-it-system
cd hhivp-it-system
chmod +x scripts/*.sh
```

### 2. Настройка окружения
```bash
cp .env.example .env
# Отредактируйте .env файл с реальными значениями
nano .env
```

### 3. Первоначальное развертывание
```bash
# Создаем сети и volumes
docker network create ito-network || true

# Запускаем базу данных
docker-compose -f docker-compose.prod.yml up -d postgres redis

# Ждем запуска БД
sleep 30

# Запускаем основные сервисы
docker-compose -f docker-compose.prod.yml up -d netbox vaultwarden bookstack

# Ждем инициализации
sleep 60

# Запускаем прокси и бота
docker-compose -f docker-compose.prod.yml up -d nginx-proxy telegram-bot
```

### 4. Первоначальная настройка

#### NetBox (netbox.hhivp.com)
- Войти как admin/пароль_из_env
- Создать API токен: Admin → API Tokens → Add
- Обновить NETBOX_API_TOKEN в .env

#### Vaultwarden (vault.hhivp.com)
- Создать аккаунт администратора
- Настроить организацию для команды

#### BookStack (docs.hhivp.com)  
- Войти как admin@admin.com/password
- Изменить пароль и email
- Создать API токен: Settings → API Tokens
- Обновить BOOKSTACK_API_TOKEN в .env

### 5. SSL сертификаты
```bash
# Через Nginx Proxy Manager (порт 81)
# Добавить каждый домен и получить Let's Encrypt сертификат
```

### 6. Резервное копирование
```bash
# Настроить cron для backup скриптов
crontab -e
# Добавить:
# 0 2 * * * /opt/hhivp-it-system/scripts/backup.sh
```

## Мониторинг и логи

```bash
# Статус всех сервисов
docker-compose -f docker-compose.prod.yml ps

# Логи конкретного сервиса
docker-compose -f docker-compose.prod.yml logs -f telegram-bot

# Логи всех сервисов
docker-compose -f docker-compose.prod.yml logs -f
```

## Обновление системы

```bash
cd /opt/hhivp-it-system
git pull
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d --build
```
