# ✅ VPS Deployment Checklist

## 🚀 Быстрый чеклист развертывания

### 📋 Предварительная подготовка
- [ ] VPS с Ubuntu 20.04+ готов
- [ ] SSH доступ настроен
- [ ] Домен настроен (если нужен)

### 🔧 Установка зависимостей
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl wget python3 python3-pip python3-venv
# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh get-docker.sh
sudo usermod -aG docker $USER && newgrp docker
```

### 📦 Клонирование и настройка
```bash
cd /opt
sudo git clone https://github.com/YOUR_USERNAME/tg-mordern-bot.git
sudo chown -R $USER:$USER tg-mordern-bot
cd tg-mordern-bot
cp .env.example .env.prod
nano .env.prod  # Настроить токены и пароли
```

### 🐳 Развертывание
```bash
./deploy-prod.sh
# Следовать инструкциям скрипта
```

### ✅ Проверка
```bash
docker-compose -f docker-compose.prod.yml ps
docker-compose -f docker-compose.prod.yml logs -f bot
# Тест в Telegram: /start
```

### 🔄 Автозапуск
```bash
sudo cp hhivp-bot.service /etc/systemd/system/
sudo systemctl enable hhivp-bot.service
sudo systemctl start hhivp-bot.service
```

## 🛠️ Команды управления

### Основные
```bash
# Запуск
docker-compose -f docker-compose.prod.yml up -d

# Остановка  
docker-compose -f docker-compose.prod.yml down

# Логи
docker-compose -f docker-compose.prod.yml logs -f

# Статус
docker-compose -f docker-compose.prod.yml ps

# Обновление
./update.sh
```

### Обслуживание
```bash
# Бэкап БД
docker-compose -f docker-compose.prod.yml exec postgres pg_dump -U bot_user telegram_bot_prod > backup.sql

# Мониторинг
./monitor.sh

# Перезапуск только бота
docker-compose -f docker-compose.prod.yml restart bot
```

## 🆘 Если что-то не работает

1. **Проверить логи:** `docker-compose -f docker-compose.prod.yml logs`
2. **Проверить статус:** `docker-compose -f docker-compose.prod.yml ps`  
3. **Перезапустить:** `docker-compose -f docker-compose.prod.yml restart`
4. **Полная пересборка:** `docker-compose -f docker-compose.prod.yml build --no-cache`

## 📞 Контакты для поддержки

- Документация: `VPS_DEPLOYMENT_GUIDE.md`
- Логи: `/opt/tg-mordern-bot/logs/`
- Бэкапы: `/opt/tg-mordern-bot/backups/`

---

**🎯 Цель: Работающий бот на VPS за 30 минут!**
