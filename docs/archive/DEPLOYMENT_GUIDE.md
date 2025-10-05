# 🚀 РУКОВОДСТВО ПО РАЗВЕРТЫВАНИЮ

> **Полное руководство по развертыванию Modern Telegram Bot в продакшн и разработке**

---

## ⚡ Быстрое развертывание

### 🎯 **За 5 минут до рабочего бота:**

```bash
# 1. Клонируем репозиторий
git clone https://github.com/zarudesu/tg-modern-bot.git
cd tg-modern-bot

# 2. Настраиваем переменные окружения
cp .env.example .env
nano .env  # Отредактируйте обязательные параметры

# 3. Запускаем в режиме разработки
make dev   # БД в Docker, бот локально

# 4. Проверяем работу
make status
# Отправьте /start вашему боту в Telegram
```

**🎉 Готово! Бот работает и готов к использованию.**

---

## 🔧 Обязательная конфигурация

### ⚙️ **Минимальные настройки .env:**

```bash
# ОБЯЗАТЕЛЬНО настроить:
TELEGRAM_TOKEN=1234567890:ABCdefGHijklmNOpqrsTUvwxYZ  # От @BotFather
ADMIN_USER_IDS=123456789,987654321                      # Ваши Telegram ID

# Остальное работает с дефолтами:
DATABASE_URL=postgresql+asyncpg://bot_user:bot_password@localhost:5432/telegram_bot
REDIS_URL=redis://:redis_password@localhost:6379/0
```

### 🔍 **Как получить Telegram ID:**
1. Отправьте сообщение боту @userinfobot
2. Или запустите бота и посмотрите в логи при отправке /start
3. Добавьте ID в ADMIN_USER_IDS через запятую

---

## 🐳 Режимы развертывания

### 1. 🔧 **Режим разработки (рекомендуется)**
```bash
make dev
```
**Что происходит:**
- PostgreSQL и Redis запускаются в Docker
- Бот запускается локально для отладки
- Автоматическая перезагрузка при изменениях
- Полные логи в консоли

**Плюсы:**
- ✅ Быстрая разработка и отладка
- ✅ Простой доступ к логам
- ✅ Легко перезапускать бот

### 2. 🐳 **Полный Docker режим**
```bash
make full-up
```
**Что происходит:**
- Все сервисы в Docker контейнерах
- Автоматические перезапуски
- Продакшн-подобное окружение

**Плюсы:**
- ✅ Полная изоляция
- ✅ Легко деплоить
- ✅ Стабильная работа

### 3. 🏭 **Продакшн развертывание**
```bash
# Настройка продакшн конфигурации
cp .env.example .env.prod
nano .env.prod

# Запуск продакшн деплоя
chmod +x deploy-prod.sh
./deploy-prod.sh
```

---

## 🗄️ База данных

### 📊 **PostgreSQL настройка:**
```bash
# Запуск только БД
make db-up

# PostgreSQL консоль
make db-shell

# Веб админка (localhost:8080)
make db-admin
# Логин: admin@admin.com / Пароль: admin
```

### 🔄 **Миграции автоматически:**
При первом запуске автоматически:
- Создаются все таблицы
- Выполняются миграции
- Добавляются индексы
- Заполняются базовые данные

### 💾 **Бэкапы:**
```bash
# Создать бэкап
docker exec -t $(docker-compose ps -q db) pg_dump -U bot_user telegram_bot > backup_$(date +%Y%m%d_%H%M%S).sql

# Восстановить из бэкапа  
docker exec -i $(docker-compose ps -q db) psql -U bot_user -d telegram_bot < backup.sql
```

---

## 🔗 Настройка интеграций

### 🌐 **n8n + Google Sheets (опционально):**

1. **Настройте n8n workflow:**
   ```bash
   # Используйте шаблон из docs/n8n-workflow-template.json
   # Импортируйте в ваш n8n экземпляр
   ```

2. **Получите webhook URL:**
   ```bash
   # Скопируйте webhook URL из n8n
   # Добавьте в .env:
   N8N_WEBHOOK_URL=https://your-n8n.com/webhook/work-journal
   ```

3. **Настройте Google Sheets:**
   ```bash
   # Создайте таблицу Google Sheets
   # Добавьте ID в .env:
   GOOGLE_SHEETS_ID=your_google_sheets_id_here
   ```

### 📋 **Структура Google Sheets:**
| Столбец | Описание | Пример |
|---------|----------|--------|
| Timestamp | Время создания | 2025-08-03 15:30:45 |
| Date | Дата работ | 2025-08-03 |
| Company | Компания | Ива |
| Duration | Время работы | 45 мин |
| Description | Описание | Настройка сервера |
| Travel | Выезд | Нет |
| Workers | Исполнители | Тимофей, Дима |
| Creator | Создатель | Kostya |

---

## 🛠️ Полезные команды

### 🔄 **Управление сервисами:**
```bash
# Статус всех контейнеров
make status

# Логи всех сервисов
make logs

# Только логи бота
make logs-bot

# Остановить все
make down

# Перезапустить бот
make restart-bot
```

### 🧪 **Тестирование:**
```bash
# Базовые тесты
python test_basic.py

# Тесты бота  
python test_bot.py

# Тесты модуля журнала
python test_work_journal.py

# Все тесты
make test
```

### 🧹 **Очистка:**
```bash
# Очистить временные файлы
make clean

# ОСТОРОЖНО: Полная очистка (удалит все данные!)
make full-clean
```

---

## 🏭 Продакшн развертывание

### 🔒 **Продакшн .env конфигурация:**
```bash
# Основные настройки
TELEGRAM_TOKEN=your_production_bot_token
ADMIN_USER_IDS=123456789,987654321

# Продакшн база данных
DATABASE_URL=postgresql+asyncpg://prod_user:strong_password@prod_db:5432/telegram_bot
REDIS_URL=redis://:strong_redis_password@prod_redis:6379/0

# Интеграции
N8N_WEBHOOK_URL=https://your-n8n.com/webhook/work-journal
GOOGLE_SHEETS_ID=your_production_sheets_id

# Безопасность и производительность
LOG_LEVEL=INFO
RATE_LIMIT_DEFAULT=10/minute
SESSION_TIMEOUT=3600
```

### 🐳 **Docker Compose продакшн:**
```bash
# Запуск с продакшн конфигурацией
docker-compose --env-file .env.prod -f docker-compose.prod.yml up -d

# Проверка статуса
docker-compose --env-file .env.prod -f docker-compose.prod.yml ps

# Логи продакшн
docker-compose --env-file .env.prod -f docker-compose.prod.yml logs -f bot
```

### 📊 **Мониторинг продакшн:**
```bash
# Health check
curl http://localhost:8000/health

# Метрики
curl http://localhost:8080/metrics

# Статус сервисов
make status
```

---

## 🔧 Troubleshooting

### ❌ **Частые проблемы и решения:**

#### **1. Бот не отвечает**
```bash
# Проверьте логи
make logs-bot

# Проверьте токен
echo $TELEGRAM_TOKEN

# Проверьте доступ к API
curl -s "https://api.telegram.org/bot${TELEGRAM_TOKEN}/getMe"
```

#### **2. База данных не подключается**
```bash
# Проверьте статус БД
make status

# Перезапустите БД
make db-restart

# Проверьте подключение
make db-shell
```

#### **3. Админ не может использовать бота**
```bash
# Проверьте ADMIN_USER_IDS в .env
cat .env | grep ADMIN_USER_IDS

# Получите свой Telegram ID
# Отправьте /start боту и проверьте логи
make logs-bot
```

#### **4. Docker проблемы**
```bash
# Перезапуск всех сервисов
make down && make dev

# Очистка Docker
docker system prune

# Пересборка образов
docker-compose build --no-cache
```

---

## 📈 Масштабирование

### ⚡ **Увеличение производительности:**

#### **1. База данных:**
```bash
# В docker-compose.yml увеличьте ресурсы:
services:
  db:
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G
```

#### **2. Redis кэш:**
```bash
# Увеличьте memory для Redis:
services:
  redis:
    command: redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru
```

#### **3. Бот:**
```bash
# Настройте ограничения в .env:
RATE_LIMIT_DEFAULT=20/minute
MAX_SEARCH_RESULTS=50
SESSION_TIMEOUT=7200
```

### 🔄 **Горизонтальное масштабирование:**
- Используйте несколько инстансов бота за балансировщиком
- Вынесите PostgreSQL на отдельный сервер
- Используйте Redis Cluster для кэширования

---

## 🔒 Безопасность в продакшн

### 🛡️ **Рекомендации по безопасности:**

#### **1. Переменные окружения:**
```bash
# Используйте сильные пароли
DATABASE_URL=postgresql+asyncpg://user:STRONG_RANDOM_PASSWORD@db:5432/db
REDIS_URL=redis://:STRONG_RANDOM_PASSWORD@redis:6379/0

# Ограничьте админов
ADMIN_USER_IDS=123456789  # Только проверенные ID
```

#### **2. Сетевая безопасность:**
```bash
# В docker-compose.prod.yml не экспонируйте ненужные порты
services:
  db:
    ports: []  # Не экспонировать наружу
  redis:
    ports: []  # Не экспонировать наружу
```

#### **3. Логирование:**
```bash
# Настройте ротацию логов
LOG_LEVEL=INFO  # Не DEBUG в продакшн
MAX_LOG_SIZE=100MB
LOG_RETENTION=30d
```

---

## 📋 Чек-лист развертывания

### ✅ **Перед продакшн запуском:**

#### **Обязательно:**
- [ ] Настроен правильный TELEGRAM_TOKEN
- [ ] Указаны корректные ADMIN_USER_IDS  
- [ ] Сильные пароли для БД и Redis
- [ ] Настроены бэкапы БД
- [ ] Проверена работа через /start
- [ ] Протестированы основные команды

#### **Рекомендуется:**
- [ ] Настроена интеграция с n8n
- [ ] Подключен Google Sheets
- [ ] Настроен мониторинг
- [ ] Настроены уведомления об ошибках
- [ ] Документированы процедуры восстановления

#### **Дополнительно:**
- [ ] Настроен reverse proxy (nginx)
- [ ] SSL сертификаты
- [ ] Firewall правила
- [ ] Мониторинг ресурсов сервера

---

## 🎯 Заключение

### ✅ **Готово к использованию:**
Следуя этому руководству, вы получите полностью рабочий Telegram бот с:
- ✅ Стабильной архитектурой
- ✅ Полнофункциональным журналом работ
- ✅ Готовыми интеграциями
- ✅ Продакшн-готовой конфигурацией

### 🚀 **Следующие шаги:**
1. Разверните бот по этому руководству
2. Протестируйте основную функциональность
3. Настройте интеграции при необходимости
4. Запустите в продакшн

**💡 Совет:** Начните с режима разработки (`make dev`), протестируйте все функции, а затем переходите к продакшн развертыванию.

---

*📅 Обновлено: 3 августа 2025*  
*📖 Версия руководства: 1.1.0*  
*🎯 Статус: Готово к использованию*