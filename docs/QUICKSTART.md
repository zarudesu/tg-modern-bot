# 🚀 Быстрый старт HHIVP IT-Outsource System

## Что у нас есть

✅ **Готовая архитектура системы**
✅ **Docker-конфигурации для всех сервисов**  
✅ **Telegram-бот с поиском по всем системам**
✅ **Скрипты автоматического развертывания**
✅ **Резервное копирование**

## Следующие шаги

### 1. **Нужно узнать SMTP настройки** 
Для `info@hhivp.com` уточните у хостинг-провайдера:
- SMTP сервер (обычно `mail.hhivp.com`)
- Порт (587 или 465)
- Пароль от почты

### 2. **Развертывание на сервере**

```bash
# Клонирование проекта
cd /opt
git clone <your-repo> hhivp-it-system
cd hhivp-it-system

# Настройка окружения
cp .env.example .env
nano .env  # Заполните SMTP настройки

# Автоматическое развертывание
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

### 3. **Настройка доменов**

В DNS настройте A-записи:
- `netbox.hhivp.com` → IP сервера
- `vault.hhivp.com` → IP сервера  
- `docs.hhivp.com` → IP сервера

### 4. **SSL сертификаты**

После развертывания:
1. Откройте http://your-server:81 (Nginx Proxy Manager)
2. Войдите: admin@example.com / changeme
3. Добавьте каждый домен с Let's Encrypt

### 5. **API токены**

После настройки SSL:
1. **NetBox** (https://netbox.hhivp.com): Admin → API Tokens
2. **BookStack** (https://docs.hhivp.com): Settings → API Tokens  
3. Обновите токены в `.env`
4. Перезапустите бота: `docker-compose -f docker-compose.simple.yml restart telegram-bot`

## Доступные сервисы

🌐 **NetBox**: https://netbox.hhivp.com (документирование сетей)
🔐 **Vaultwarden**: https://vault.hhivp.com (менеджер паролей)
📚 **BookStack**: https://docs.hhivp.com (база знаний)
🤖 **Telegram Bot**: @hhivp_it_bot

## Команды управления

```bash
# Статус всех сервисов
docker-compose -f docker-compose.simple.yml ps

# Логи конкретного сервиса  
docker-compose -f docker-compose.simple.yml logs -f telegram-bot

# Перезапуск сервиса
docker-compose -f docker-compose.simple.yml restart netbox

# Резервное копирование
./scripts/backup.sh

# Остановка всех сервисов
docker-compose -f docker-compose.simple.yml down

# Запуск всех сервисов
docker-compose -f docker-compose.simple.yml up -d
```

## Использование Telegram-бота

```
🔍 Поиск:
/search клиент название
/ip 192.168.1.1
/device router01
/client ООО Ромашка
/password router admin

📊 Статус:
/status - статус всех систем
/help - справка

👑 Администрирование:
/admin - панель администратора
/stats - статистика
/backup - создать backup
```

## Безопасность

- ✅ Все пароли зашифрованы в Vaultwarden
- ✅ SSL сертификаты для всех доменов  
- ✅ Логирование всех действий
- ✅ Доступ к боту только для авторизованных пользователей
- ✅ Регулярное резервное копирование

## Мониторинг

📊 **Логи**: `/opt/hhivp-it-system/logs/`
💾 **Backup**: `/opt/hhivp-it-system/backup/`
🔧 **Конфигурация**: `/opt/hhivp-it-system/.env`

## Поддержка

При проблемах проверьте:
1. `docker-compose -f docker-compose.simple.yml ps` - статус контейнеров
2. `docker-compose -f docker-compose.simple.yml logs service_name` - логи
3. `.env` файл - корректность настроек
4. DNS записи доменов
5. SSL сертификаты в Nginx Proxy Manager

---

🎉 **Система готова к продуктивному использованию!**
