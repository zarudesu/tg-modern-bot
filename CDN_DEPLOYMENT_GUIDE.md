# 🚀 Инструкция по деплою на CDN сервер

## 📋 Подготовка к деплою

### 1. **На CDN сервере клонируем/обновляем репозиторий:**

```bash
# Если репозиторий еще не клонирован:
git clone https://github.com/zarudesu/tg-modern-bot.git
cd tg-modern-bot

# Если репозиторий уже есть:
cd tg-modern-bot
git pull origin main
```

### 2. **Настройка продакшн окружения:**

```bash
# Копируем продакшн конфигурацию
cp .env.prod .env

# Проверяем настройки (все должно быть готово)
cat .env
```

### 3. **Установка зависимостей:**

```bash
# Создаем виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Устанавливаем зависимости
pip install -r requirements.txt
```

## 🐳 Деплой с Docker (Рекомендуемый)

### 1. **Быстрый деплой:**
```bash
# Запуск продакшн версии
./deploy-prod.sh
```

### 2. **Проверка статуса:**
```bash
# Статус контейнеров
docker-compose -f docker-compose.prod.yml ps

# Логи бота
docker-compose -f docker-compose.prod.yml logs -f bot

# Логи базы данных
docker-compose -f docker-compose.prod.yml logs -f postgres
```

## 🔧 Ручной деплой (Альтернатива)

### 1. **База данных:**
```bash
# Запуск только БД
docker-compose -f docker-compose.database.yml up -d postgres redis
```

### 2. **Запуск бота:**
```bash
# Через продакшн менеджер
./bot_manager_prod.sh start

# Или через обычный менеджер
./bot_manager.sh start
```

## 📊 Проверка работоспособности

### 1. **Тестирование основных функций:**

```bash
# Тест подключения к n8n
python test_n8n_final.py

# Тест группового чата
python test_group_notification.py

# Тест парсера времени
python test_duration_issue.py
```

### 2. **Проверка в Telegram:**
- Отправьте `/start` боту @hhivp_it_bot
- Создайте тестовую запись через `/journal`
- Проверьте что уведомление пришло в группу "BIOS АйТи Решения"
- Убедитесь что данные попали в Google Sheets

## 🔍 Мониторинг

### **Логи:**
```bash
# Логи бота в реальном времени
tail -f logs/bot_manager.log

# Docker логи
docker-compose -f docker-compose.prod.yml logs -f bot

# Статус процессов
./bot_manager.sh status
```

### **Полезные команды:**
```bash
# Перезапуск бота
./bot_manager.sh restart

# Остановка всех сервисов
docker-compose -f docker-compose.prod.yml down

# Полная очистка и перезапуск
docker-compose -f docker-compose.prod.yml down -v
./deploy-prod.sh
```

## ⚠️ Troubleshooting

### **Если бот не отвечает:**
1. Проверьте логи: `docker-compose -f docker-compose.prod.yml logs bot`
2. Проверьте статус: `./bot_manager.sh status`
3. Перезапустите: `./bot_manager.sh restart`

### **Если не работают уведомления в группу:**
1. Проверьте `WORK_JOURNAL_GROUP_CHAT_ID` в `.env`
2. Убедитесь что бот добавлен в группу
3. Протестируйте: `python test_group_notification.py`

### **Если не работает n8n интеграция:**
1. Проверьте `N8N_WEBHOOK_URL` в `.env`
2. Протестируйте: `python test_n8n_final.py`
3. Проверьте доступность n8n: `curl https://your-n8n-instance.com/webhook/work-journal`

## 🎯 **Финальная проверка деплоя:**

✅ Бот отвечает на `/start`  
✅ Создание записи через `/journal` работает  
✅ Уведомления приходят в группу с кликабельной ссылкой  
✅ Данные попадают в Google Sheets как числа без кавычек  
✅ Время корректно конвертируется в минуты  

## 📞 **Контакты для поддержки:**

- **Telegram:** @zardes
- **Группа уведомлений:** "BIOS АйТи Решения"
- **Google Sheets:** [Ссылка на таблицу](https://docs.google.com/spreadsheets/d/YOUR_GOOGLE_SHEETS_ID/edit?usp=drivesdk)

---

**🚀 Бот готов к продакшн использованию!**
