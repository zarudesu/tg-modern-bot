# 👥 Система упоминаний исполнителей

## 🎯 Назначение

Система упоминаний позволяет автоматически уведомлять исполнителей о назначенных им работах через Telegram упоминания (@username) и личные сообщения.

## ✨ Основные возможности

### 📢 Уведомления в чате
- **Автоматические упоминания** исполнителей при создании записи в журнале работ
- **Детализированная информация** о работе прямо в сообщении
- **Указание создателя записи** для контроля кто что назначил

### 💬 Личные уведомления (опционально)
- **Персональные сообщения** исполнителям в ЛС
- **Настройки пользователя** - можно включить/отключить
- **Полная информация** о назначенной работе

### ⚙️ Гибкие настройки
- **Управление упоминаниями** на уровне каждого исполнителя
- **Настройки уведомлений** для каждого пользователя
- **Связка Telegram username и User ID** для точных упоминаний

## 🏗️ Архитектура системы

### Компоненты
```
app/services/worker_mention_service.py     # Основной сервис упоминаний
app/database/work_journal_models.py       # Модели данных
app/handlers/work_journal.py              # Интеграция с обработчиками
```

### Модели данных

#### WorkJournalWorker
```sql
CREATE TABLE work_journal_workers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    telegram_username VARCHAR(255),           -- username без @
    telegram_user_id BIGINT,                 -- Telegram User ID для точных упоминаний
    mention_enabled BOOLEAN DEFAULT TRUE,     -- Включены ли упоминания
    display_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### UserNotificationPreferences
```sql
CREATE TABLE user_notification_preferences (
    id SERIAL PRIMARY KEY,
    telegram_user_id BIGINT NOT NULL UNIQUE,
    enable_work_assignment_notifications BOOLEAN DEFAULT FALSE,  -- ЛС уведомления
    enable_mentions_in_chat BOOLEAN DEFAULT TRUE,               -- Упоминания в чате
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

## 👥 Настройка исполнителей

### Текущие исполнители

| Имя | Username | User ID | Упоминания |
|-----|----------|---------|------------|
| Константин Макейкин | @zardes | 28795547 | ✅ |
| Гусев Дима | @strikerstr | NULL | ✅ |
| Тимофей Батырев | @spiritphoto | NULL | ✅ |

### Добавление нового исполнителя
```sql
INSERT INTO work_journal_workers (
    name, 
    telegram_username, 
    telegram_user_id, 
    mention_enabled
) VALUES (
    'Новый Исполнитель',
    'new_username',      -- без @
    123456789,           -- Telegram User ID (опционально)
    TRUE
);
```

## 📱 Как работает система

### 1. Создание записи в журнале
```
Пользователь создает запись → Выбирает исполнителей → Подтверждает сохранение
```

### 2. Обработка упоминаний
```python
# В handle_confirm_save()
mention_service = WorkerMentionService(session, bot)
success, errors = await mention_service.send_work_assignment_notifications(
    entry, creator_name, callback.message.chat.id
)
```

### 3. Отправка уведомлений
1. **Получение данных исполнителей** из БД
2. **Формирование сообщения** с упоминаниями
3. **Отправка в чат** с @упоминаниями
4. **Отправка ЛС уведомлений** (если включено у пользователя)

## 💬 Примеры сообщений

### Сообщение в чате с упоминаниями
```
📋 **Новая запись в журнале работ**

👥 **Исполнители:** @zardes, @strikerstr, @spiritphoto
🏢 **Компания:** Ива
📅 **Дата:** 01.08.2025
⏱ **Время:** 45 мин
🚗 **Тип:** Выезд

📝 **Описание:**
Настройка нового рабочего места в офисе

👤 **Создал:** Kostya
```

### Личное сообщение исполнителю
```
🔔 **Вам назначена работа**

🏢 **Компания:** Ива
📅 **Дата:** 01.08.2025
⏱ **Время:** 45 мин
🚗 **Тип:** Выезд

📝 **Описание:**
Настройка нового рабочего места в офисе

👤 **Назначил:** Kostya

_Для отключения уведомлений используйте /settings_
```

## ⚙️ Управление настройками

### Команды для пользователей
```
/settings - Настройки уведомлений (планируется)
```

### Программное управление
```python
# Включить/отключить ЛС уведомления
await mention_service.set_user_notification_preferences(
    telegram_user_id=123456789,
    enable_work_assignments=True,
    enable_mentions=True
)

# Получить настройки пользователя
prefs = await mention_service.get_user_notification_preferences(123456789)
```

## 🔧 API сервиса

### WorkerMentionService

#### Основные методы

##### get_worker_mentions(worker_names: List[str])
```python
"""Получить данные для упоминаний исполнителей"""
mentions = await mention_service.get_worker_mentions(["Тимофей", "Дима"])
# Возвращает: List[Dict] с данными для упоминаний
```

##### send_work_assignment_notifications(entry, creator_name, chat_id)
```python
"""Отправить уведомления о назначении работы"""
success, errors = await mention_service.send_work_assignment_notifications(
    entry, "Kostya", -1001234567890
)
# Возвращает: Tuple[bool, List[str]] - успех и список ошибок
```

##### set_user_notification_preferences(user_id, **kwargs)
```python
"""Установить настройки уведомлений пользователя"""
prefs = await mention_service.set_user_notification_preferences(
    telegram_user_id=123456789,
    enable_work_assignments=True
)
```

## 🚀 Интеграция с обработчиками

### В work_journal.py
```python
# После сохранения записи в БД
try:
    from ..services.worker_mention_service import WorkerMentionService
    from aiogram import Bot
    from ..config import settings
    
    bot = Bot(token=settings.telegram_token)
    mention_service = WorkerMentionService(session, bot)
    
    # Отправляем уведомления в чат
    success, errors = await mention_service.send_work_assignment_notifications(
        entry, creator_name, callback.message.chat.id
    )
    
    if errors:
        for error in errors[:2]:  # Показываем только первые 2 ошибки
            bot_logger.warning(f"Mention notification error: {error}")
            
except Exception as e:
    bot_logger.error(f"Error sending mention notifications: {e}")
    # Не прерываем процесс, так как основная задача выполнена
```

## 📊 Мониторинг и логирование

### Логирование
- **Успешные отправки** уведомлений в chat
- **Персональные уведомления** каждому исполнителю
- **Ошибки отправки** с детализацией
- **Настройки пользователей** изменения

### Примеры логов
```
INFO - Work assignment notification sent to chat -1001234567890
INFO - Personal notification sent to Тимофей (123456789)
WARNING - Failed to send personal notification to Дима: user not found
ERROR - Error sending mention notifications: Bot was blocked by user
```

## 🛠️ Настройка для новых чатов

### Добавление бота в групповой чат
1. Добавить бота в групповой чат
2. Выдать права на отправку сообщений
3. Получить chat_id группы
4. Проверить работу упоминаний

### Получение chat_id
```python
# В любом обработчике
print(f"Chat ID: {message.chat.id}")
# Или через бота
await message.answer(f"Chat ID этого чата: {message.chat.id}")
```

## 🔮 Планируемые улучшения

### v1.2 (Следующий этап)
- [ ] **Команда /settings** для настройки уведомлений
- [ ] **Групповые упоминания** нескольких исполнителей одновременно
- [ ] **Отчеты по уведомлениям** кто получил, кто нет

### v1.3 (Будущее)
- [ ] **Временные зоны** для уведомлений
- [ ] **Шаблоны сообщений** настраиваемые администраторами
- [ ] **Эскалация уведомлений** если исполнитель не ответил

## 🐛 Обработка ошибок

### Типичные ошибки и решения

#### "Failed to send personal notification: Bot was blocked by user"
**Причина:** Пользователь заблокировал бота в ЛС  
**Решение:** Автоматически отключать ЛС уведомления для таких пользователей

#### "Chat not found"
**Причина:** Неверный chat_id или бот не добавлен в чат  
**Решение:** Проверить права бота в групповом чате

#### "Username not found"
**Причина:** Пользователь изменил username  
**Решение:** Использовать User ID вместо username

### Graceful degradation
Система спроектирована так, что ошибки уведомлений **не влияют** на основной процесс создания записи в журнале работ. Запись всегда сохраняется в БД, а ошибки уведомлений только логируются.

## 📋 Контрольный список настройки

### Для нового проекта:
- [ ] Создать таблицы `work_journal_workers` и `user_notification_preferences`
- [ ] Добавить исполнителей с их Telegram данными
- [ ] Добавить бота в групповой чат
- [ ] Протестировать создание записи с упоминаниями
- [ ] Настроить логирование уведомлений
- [ ] Документировать chat_id для проекта

### Для существующего проекта:
- [ ] Обновить схему БД миграциями
- [ ] Проверить актуальность username исполнителей
- [ ] Протестировать упоминания в текущем чате
- [ ] Обновить документацию проекта

---

**🎯 Система упоминаний готова к использованию и расширению!**