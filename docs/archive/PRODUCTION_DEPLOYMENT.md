# 🚀 PRODUCTION DEPLOYMENT GUIDE

**Дата:** 03.08.2025  
**Версия:** 1.1.0  
**Проект:** HHIVP IT Assistant  

---

## 🎯 Подготовка к Production

### ✅ **Что уже готово:**
- ✅ Все функции бота протестированы и работают
- ✅ База данных настроена и оптимизирована
- ✅ Docker контейнеры готовы к production
- ✅ Логирование и мониторинг настроены
- ✅ Система управления компаниями реализована
- ✅ Интеграция с n8n и Google Sheets готова

---

## 🛠️ Настройка Production среды

### **1. Подготовка сервера**
```bash
# Установка Docker и Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Установка Docker Compose
sudo pip3 install docker-compose
```

### **2. Клонирование проекта**
```bash
git clone https://github.com/your-repo/tg-modern-bot.git
cd tg-modern-bot
```

### **3. Настройка переменных окружения**
```bash
# Копирование production конфигурации
cp .env.prod .env.prod.local

# Редактирование конфигурации
nano .env.prod.local
```

**Обязательные переменные для изменения:**
```bash
# Telegram Bot Token из @BotFather
TELEGRAM_TOKEN=your_production_bot_token

# ID администраторов (ваш Telegram ID)
ADMIN_USER_IDS=YOUR_TELEGRAM_ID

# Безопасные пароли для БД
POSTGRES_PASSWORD=secure_production_password_here
REDIS_PASSWORD=secure_redis_password_here

# n8n интеграция (если настроена)
N8N_WEBHOOK_URL=https://your-n8n.com/webhook/work-journal
GOOGLE_SHEETS_ID=your_google_sheets_id
```

---

## 🚀 Развертывание

### **Автоматическое развертывание (рекомендуется):**
```bash
# Запуск полного автоматического развертывания
make prod-deploy
```

### **Ручное развертывание:**
```bash
# 1. Остановка старых версий
make prod-down

# 2. Создание бэкапа (если БД существует)
make prod-backup

# 3. Сборка и запуск
make prod-up

# 4. Проверка статуса
make prod-status
```

---

## 📊 Мониторинг и управление

### **Основные команды:**
```bash
# Статус всех сервисов
make prod-status

# Просмотр логов бота
make prod-logs

# Создание бэкапа БД
make prod-backup

# Перезапуск бота
docker-compose -f docker-compose.prod.yml restart bot

# Остановка всех сервисов
make prod-down
```

### **Проверка работоспособности:**
```bash
# Проверка контейнеров
docker ps

# Проверка логов
docker-compose -f docker-compose.prod.yml logs bot

# Проверка базы данных
docker exec -it hhivp-bot-postgres-prod psql -U hhivp_bot -d hhivp_bot_prod
```

---

## 🔧 Troubleshooting

### **Проблема: Бот не отвечает**
```bash
# Проверить логи
make prod-logs

# Перезапустить бота
docker-compose -f docker-compose.prod.yml restart bot
```

### **Проблема: База данных недоступна**
```bash
# Проверить статус PostgreSQL
docker-compose -f docker-compose.prod.yml ps postgres

# Проверить логи БД
docker-compose -f docker-compose.prod.yml logs postgres
```

### **Проблема: Нет места на диске**
```bash
# Очистка старых Docker образов
docker system prune -f

# Очистка логов
truncate -s 0 logs/*.log
```

---

## 🔐 Безопасность

### **Настройки безопасности:**
- ✅ Бот работает под непривилегированным пользователем
- ✅ База данных изолирована в Docker сети
- ✅ Логи не содержат чувствительной информации
- ✅ Rate limiting настроен для защиты от спама

### **Рекомендации:**
1. **Регулярные бэкапы** - используйте `make prod-backup`
2. **Мониторинг логов** - следите за `make prod-logs`
3. **Обновления** - регулярно обновляйте зависимости
4. **Firewall** - ограничьте доступ к портам БД

---

## 📈 Масштабирование

### **Для высокой нагрузки:**
1. **Увеличение ресурсов контейнеров**
2. **Настройка connection pooling**
3. **Horizontal scaling с несколькими экземплярами**
4. **Использование внешних БД (PostgreSQL cluster)**

---

## 🎉 Запуск одной командой

### **Все сразу (для первого деплоя):**
```bash
make prod-deploy
```

### **Проверка работы:**
```bash
# 1. Проверить статус
make prod-status

# 2. Открыть Telegram
# 3. Найти бота @hhivp_it_bot
# 4. Отправить /start
# 5. Проверить, что появились кнопки меню
```

---

## 📋 Checklist готовности к Production

### ✅ **Технические требования:**
- [x] Docker и Docker Compose установлены
- [x] Порты 5432 и 6379 свободны
- [x] Минимум 2GB RAM и 10GB диска
- [x] Настроены переменные окружения

### ✅ **Конфигурация бота:**
- [x] Production токен от @BotFather
- [x] ID администраторов указаны
- [x] Безопасные пароли установлены
- [x] n8n интеграция настроена (опционально)

### ✅ **Безопасность:**
- [x] Пароли БД изменены с дефолтных
- [x] Firewall настроен
- [x] Резервное копирование настроено

---

**🚀 Готов к запуску в Production!**  
**📱 Бот: @hhivp_it_bot**  
**🏢 Для: HHIVP IT Management**  
**📅 Дата готовности: 03.08.2025**
