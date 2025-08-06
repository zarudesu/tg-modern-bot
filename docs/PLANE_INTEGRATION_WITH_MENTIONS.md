# 🎯 Интеграция Plane с системой упоминаний исполнителей

## 🎯 Назначение

Интеграция позволяет автоматически уведомлять исполнителей в Telegram при создании и обновлении задач в Plane с использованием системы упоминаний вместо полных имен.

## ✨ Основные возможности

### 📢 Преобразование уведомлений
- **Автоматическая замена** полных имен на Telegram упоминания
- **Пример:** "Dmitriy Gusev" → "@strikerstr"
- **Дублирование уведомлений** в ЛС исполнителям (опционально)

### 🎨 Стилизованные сообщения
```
╭─ 🎯 **HARZL-19**
├ 📝 Принтер на складе добавить в принтсервер прикрутить политику
├ 📁 HarzLabs
├ ⚪ Без приоритета
├ 📅 31.07.2025 23:38
├ 👥 @strikerstr  ← вместо "Dmitriy Gusev"
├ 📊 Todo
╰─ 🔗 Открыть в Plane
```

### 💬 Личные уведомления
```
🎯 **Вам назначена задача**

📝 **Принтер на складе добавить в принтсервер прикрутить политику**

📁 **Проект:** HarzLabs
⚪ **Приоритет:** None
📝 **Статус:** Todo
📅 **Дата:** 31.07.2025 23:38

📋 **Описание:**
Настройка принтера для работы с принт-сервером и применение политик печати

🔗 [Открыть задачу](https://plane.hhivp.com/projects/HarzLabs/issues/HARZL-19)

_Для отключения уведомлений используйте /settings_
```

## 🏗️ Архитектура

### Компоненты
```
app/integrations/plane_with_mentions.py    # Основной сервис с упоминаниями
app/handlers/plane_testing.py              # Команды тестирования
app/webhooks/server.py                      # Webhook сервер
sql/init_plane_workers.sql                 # Инициализация данных
```

### Интеграция с существующей системой
- **WorkerMentionService** - для упоминаний и ЛС уведомлений
- **work_journal_workers** - маппинг пользователей Plane
- **user_notification_preferences** - настройки пользователей

## 👥 Маппинг исполнителей

### Структура данных
```sql
-- Добавлено поле plane_user_names в work_journal_workers
ALTER TABLE work_journal_workers 
ADD COLUMN plane_user_names TEXT;

-- Пример данных
UPDATE work_journal_workers 
SET plane_user_names = '["Dmitriy Gusev", "Dmitry Gusev", "Dima Gusev"]'
WHERE name = 'Гусев Дима';
```

### Текущий маппинг

| Системное имя | Telegram | Plane имена |
|---------------|----------|-------------|
| Константин Макейкин | @zardes | Konstantin Makeykin, Kostya Makeykin, Константин Макейкин |
| Гусев Дима | @strikerstr | Dmitriy Gusev, Dmitry Gusev, Dima Gusev |
| Тимофей Батырев | @spiritphoto | Тимофей Батырев, Timofeij Batyrev |

## ⚙️ Настройка

### 1. Переменные окружения
```bash
# .env файл
PLANE_CHAT_ID=-1001234567890  # ID чата для уведомлений
PLANE_TOPIC_ID=123           # ID топика (опционально)
PLANE_WEBHOOK_SECRET=secret   # Секрет для webhook
```

### 2. Применение миграции
```bash
# Запуск миграции для добавления plane_user_names
cd /Users/zardes/Projects/tg-mordern-bot
python -m alembic upgrade head

# Инициализация данных
psql -h localhost -p 5432 -U bot_user -d telegram_bot -f sql/init_plane_workers.sql
```

### 3. Настройка webhook в Plane
```
URL: https://your-bot-domain.com/webhooks/plane
Secret: значение PLANE_WEBHOOK_SECRET
Events: issue.created, issue.updated, issue.deleted
```

## 🧪 Тестирование

### Команды тестирования
```bash
/test_plane          # Тест создания задачи
/test_plane_update   # Тест обновления задачи  
/plane_workers       # Показать маппинг исполнителей
/plane_config        # Показать конфигурацию
```

### Пример тестирования
1. Запустите команду `/test_plane`
2. Проверьте, что в сообщении показывается `@strikerstr` вместо "Dmitriy Gusev"
3. Проверьте, что Дмитрий получил ЛС уведомление (если включено)

## 🔧 API и интеграция

### PlaneNotificationService

#### Основные методы

##### process_webhook(payload: PlaneWebhookPayload)
```python
"""Обработка webhook от Plane"""
success = await plane_service.process_webhook(payload)
```

##### _get_assignee_mention(plane_assignee: str)
```python
"""Получение упоминания исполнителя"""
display_name, mention_data = await service._get_assignee_mention("Dmitriy Gusev")
# Возвращает: ("@strikerstr", {mention_data})
```

### PlaneWorkerMapping

#### Методы маппинга

##### get_worker_name(plane_assignee: str)
```python
"""Поиск исполнителя по имени из Plane"""
mapping = PlaneWorkerMapping(session)
worker_name = await mapping.get_worker_name("Dmitriy Gusev")
# Возвращает: "Гусев Дима"
```

## 📊 Поддерживаемые события

### issue.created
- Создание новой задачи
- Упоминание назначенного исполнителя
- ЛС уведомление исполнителю

### issue.updated
- Обновление задачи
- Показ изменений (статус, приоритет, исполнитель)
- Уведомление нового исполнителя при переназначении

### issue.deleted
- Удаление задачи
- Простое уведомление без упоминаний

## 🎨 Форматирование сообщений

### Эмодзи для приоритетов
- 🔴 Urgent
- 🟠 High  
- 🟡 Medium
- 🟢 Low
- ⚪ None

### Эмодзи для статусов
- 📋 Backlog
- 📝 Todo
- ⚡ In Progress
- 👀 In Review
- ✅ Done
- ❌ Cancelled

## 🔧 Расширение функциональности

### Добавление нового исполнителя
```sql
-- 1. Добавить в work_journal_workers
INSERT INTO work_journal_workers (
    name, 
    telegram_username, 
    telegram_user_id,
    plane_user_names,
    mention_enabled
) VALUES (
    'Новый Исполнитель',
    'new_username',
    123456789,
    '["New User", "Новый Пользователь"]',
    true
);
```

### Обновление маппинга для существующего исполнителя
```sql
-- 2. Обновить plane_user_names
UPDATE work_journal_workers 
SET plane_user_names = '["Name1", "Name2", "Name3"]'
WHERE name = 'Имя Исполнителя';
```

## 🛠️ Troubleshooting

### Частые проблемы

#### 1. Исполнитель не найден
**Проблема:** Показывается оригинальное имя вместо упоминания
**Решение:** 
- Проверить маппинг командой `/plane_workers`
- Добавить имя из Plane в `plane_user_names`
- Убедиться, что `mention_enabled = true`

#### 2. Упоминание не работает
**Проблема:** Показывается имя вместо @username
**Решение:**
- Проверить `telegram_username` в базе данных
- Убедиться, что пользователь не изменил username
- Обновить `telegram_user_id` если известен

#### 3. ЛС уведомления не приходят
**Проблема:** Упоминания работают, но ЛС нет
**Решение:**
- Проверить `telegram_user_id` исполнителя
- Убедиться, что пользователь не заблокировал бота
- Проверить настройки в `user_notification_preferences`

### Логи для отладки
```bash
# Поиск логов Plane интеграции
grep "Plane" /path/to/logs/bot.log

# Логи упоминаний
grep "mention" /path/to/logs/bot.log

# Логи webhook
grep "webhook" /path/to/logs/bot.log
```

## 📈 Мониторинг

### Метрики для отслеживания
- Количество обработанных webhook Plane
- Успешность отправки упоминаний
- Ошибки маппинга исполнителей
- Статистика ЛС уведомлений

### Пример мониторинга
```python
# В логах отслеживать:
bot_logger.info(f"Plane webhook processed: {payload.event}")
bot_logger.info(f"Worker mapped: {plane_assignee} → {worker_name}")
bot_logger.warning(f"Worker mapping failed for: {plane_assignee}")
```

## 🚀 Развертывание

### Контрольный список
- [ ] Переменные окружения настроены
- [ ] Миграция применена
- [ ] Данные исполнителей инициализированы
- [ ] Webhook настроен в Plane
- [ ] Тестирование выполнено
- [ ] Мониторинг настроен

### Production настройки
```bash
# Webhook URL для продакшена
PLANE_CHAT_ID=-1001234567890  # Реальный production чат
PLANE_WEBHOOK_SECRET=secure_production_secret

# Webhook URL в Plane
https://your-production-domain.com/webhooks/plane
```

## 🎯 Результат

После настройки системы:

### ✅ Что изменится
- **Вместо:** "👥 Исполнитель: Dmitriy Gusev"
- **Станет:** "👥 @strikerstr"

### ✅ Дополнительные возможности
- ЛС уведомления исполнителям о назначенных задачах
- Настройки уведомлений через `/settings` (когда будет реализовано)
- Отслеживание изменений исполнителей в задачах
- Унифицированная система упоминаний во всем боте

---

**🎉 Интеграция Plane с системой упоминаний готова к использованию!**