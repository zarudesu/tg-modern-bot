# ✅ Чек-лист развертывания HHIVP IT-System

## 🎯 Готово к развертыванию!

### ✅ Все настройки заполнены:
- [x] **PostgreSQL**: пароли сгенерированы
- [x] **Redis**: пароль сгенерирован  
- [x] **NetBox**: админ данные готовы
- [x] **Vaultwarden**: админ токен готов
- [x] **BookStack**: домен настроен
- [x] **SMTP**: mx.hhivp.com настроен
- [x] **Telegram**: API ID, Hash, Bot Token получены
- [x] **Домены**: hhivp.com, netbox.hhivp.com, vault.hhivp.com, docs.hhivp.com

---

## 🚀 Пошаговое развертывание

### Шаг 1: Подготовка сервера
```bash
# Установка Docker (если не установлен)
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Установка Docker Compose (если не установлен)
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### Шаг 2: Клонирование проекта
```bash
cd /opt
git clone <your-repository-url> hhivp-it-system
cd hhivp-it-system

# Копируем готовый .env файл
cp .env.example .env
# Или используйте уже готовый .env из разработки
```

### Шаг 3: Автоматическое развертывание
```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

**Скрипт автоматически:**
- Проверит зависимости
- Создаст необходимые директории
- Запустит PostgreSQL и Redis
- Инициализирует базы данных
- Запустит NetBox, Vaultwarden, BookStack
- Запустит Nginx Proxy Manager
- Соберет и запустит Telegram-бота

### Шаг 4: Настройка DNS (у регистратора домена)
Создайте A-записи:
```
netbox.hhivp.com  →  IP_ВАШЕГО_СЕРВЕРА
vault.hhivp.com   →  IP_ВАШЕГО_СЕРВЕРА  
docs.hhivp.com    →  IP_ВАШЕГО_СЕРВЕРА
```

### Шаг 5: SSL сертификаты
1. Откройте: `http://IP_СЕРВЕРА:81`
2. Войдите: `admin@example.com` / `changeme`
3. Для каждого домена:
   - Добавить Proxy Host
   - Включить SSL с Let's Encrypt
   - Переадресация на соответствующий порт

**Настройки портов:**
- `netbox.hhivp.com` → `http://netbox:8080`
- `vault.hhivp.com` → `http://vaultwarden:80`
- `docs.hhivp.com` → `http://bookstack:80`

### Шаг 6: Первоначальная настройка

#### NetBox (https://netbox.hhivp.com)
1. Войдите: `info@hhivp.com` / `NetBox$Admin2024#HHivp`
2. Перейдите: Admin → API Tokens
3. Создайте токен для бота
4. Скопируйте токен

#### BookStack (https://docs.hhivp.com)  
1. Войдите: `admin@admin.com` / `password`
2. Смените email на `info@hhivp.com` и пароль
3. Перейдите: Settings → API Tokens
4. Создайте токен для бота
5. Скопируйте токен

#### Vaultwarden (https://vault.hhivp.com)
1. Создайте первый аккаунт администратора
2. Настройте организацию для команды
3. Создайте коллекции для разных типов доступов

### Шаг 7: Обновление токенов
```bash
cd /opt/hhivp-it-system
nano .env

# Обновите:
NETBOX_API_TOKEN=ваш_токен_из_netbox
BOOKSTACK_API_TOKEN=ваш_токен_из_bookstack

# Перезапустите бота
docker-compose -f docker-compose.simple.yml restart telegram-bot
```

### Шаг 8: Тестирование
1. Найдите в Telegram: `@hhivp_it_bot`
2. Отправьте `/start`
3. Попробуйте команды:
   - `/status` - проверка систем
   - `/search тест` - проверка поиска
   - `/help` - справка

---

## 🔧 Команды управления

```bash
# Статус всех сервисов
docker-compose -f docker-compose.simple.yml ps

# Логи бота
docker-compose -f docker-compose.simple.yml logs -f telegram-bot

# Перезапуск всех сервисов
docker-compose -f docker-compose.simple.yml restart

# Создание backup
./scripts/backup.sh

# Остановка системы
docker-compose -f docker-compose.simple.yml down

# Запуск системы
docker-compose -f docker-compose.simple.yml up -d
```

---

## 🛡️ Безопасность

После развертывания:
- [ ] Смените пароли по умолчанию в Nginx Proxy Manager
- [ ] Настройте 2FA в Vaultwarden
- [ ] Ограничьте доступ к серверу через файрвол
- [ ] Настройте автоматическое резервное копирование в cron

```bash
# Добавить в cron для backup каждую ночь в 2:00
crontab -e
# Добавить строку:
0 2 * * * /opt/hhivp-it-system/scripts/backup.sh
```

---

## 🎉 Готово!

После выполнения всех шагов у вас будет:
- ✅ Централизованная система управления IT
- ✅ Безопасное хранение паролей  
- ✅ База знаний для документации
- ✅ Telegram-бот для быстрого поиска
- ✅ Автоматическое резервное копирование
- ✅ SSL шифрование для всех сервисов

**Система готова к продуктивному использованию командой HHIVP! 🚀**
