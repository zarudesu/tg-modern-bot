# ✅ Checklist настройки интеграции n8n и Google Sheets

## 📋 Пошаговый checklist для настройки

### Этап 1: Подготовка Google Sheets

- [ ] **1.1** Создать новую Google Sheets таблицу "HHIVP IT - Журнал работ"
- [ ] **1.2** Добавить заголовки столбцов:
  ```
  Timestamp | Date | Company | Duration | Description | Travel | Workers | Workers_Count | Creator | Creator_ID | Creator_Email
  ```
- [ ] **1.3** Скопировать ID таблицы из URL
- [ ] **1.4** Создать проект в Google Cloud Console
- [ ] **1.5** Включить Google Sheets API
- [ ] **1.6** Создать Service Account `n8n-sheets-integration`
- [ ] **1.7** Скачать JSON ключ Service Account
- [ ] **1.8** Предоставить Service Account права "Editor" на таблицу

**✅ Результат этапа 1:** Google Sheets готов к интеграции

---

### Этап 2: Настройка n8n Workflow

- [ ] **2.1** Открыть n8n и создать новый workflow `HHIVP-Telegram-to-Sheets`
- [ ] **2.2** Импортировать готовый template:
  ```bash
  # Использовать файл: docs/n8n-workflow-template.json
  ```
- [ ] **2.3** Настроить Webhook node:
  - [ ] HTTP Method: POST
  - [ ] Path: work-journal
  - [ ] Скопировать Webhook URL
- [ ] **2.4** Настроить Google Sheets node:
  - [ ] Добавить Service Account credentials
  - [ ] Указать Document ID (из этапа 1.3)
  - [ ] Проверить маппинг столбцов
- [ ] **2.5** Протестировать workflow кнопкой "Test"
- [ ] **2.6** Активировать workflow

**✅ Результат этапа 2:** n8n workflow активирован и работает

---

### Этап 3: Настройка Telegram Bot

- [ ] **3.1** Обновить `.env` файл:
  ```bash
  N8N_WEBHOOK_URL=https://your-n8n-instance.com/webhook/work-journal
  GOOGLE_SHEETS_ID=your_google_sheets_id_here
  ```
- [ ] **3.2** Перезапустить бота:
  ```bash
  make dev
  # или
  make full-up
  ```
- [ ] **3.3** Проверить статус бота:
  ```bash
  make status
  make logs-bot
  ```

**✅ Результат этапа 3:** Telegram Bot обновлен с новыми настройками

---

### Этап 4: Тестирование интеграции

- [ ] **4.1** Протестировать n8n webhook через curl:
  ```bash
  curl -X POST https://your-n8n-instance.com/webhook/work-journal \
    -H "Content-Type: application/json" \
    -d @docs/test-payload.json
  ```
- [ ] **4.2** Запустить тест-скрипт:
  ```bash
  python test_n8n_integration.py https://your-n8n-instance.com/webhook/work-journal
  ```
- [ ] **4.3** Проверить появление записи в Google Sheets
- [ ] **4.4** Протестировать через Telegram Bot:
  ```
  /journal
  # Заполнить все поля и подтвердить
  ```
- [ ] **4.5** Проверить новую запись в Google Sheets
- [ ] **4.6** Проверить логи n8n workflow
- [ ] **4.7** Проверить логи Telegram Bot

**✅ Результат этапа 4:** Полная интеграция работает корректно

---

### Этап 5: Финальная проверка

- [ ] **5.1** Создать 3-5 тестовых записей через разные компании
- [ ] **5.2** Проверить корректность всех данных в Google Sheets:
  - [ ] Даты в правильном формате
  - [ ] Компании отображаются корректно
  - [ ] Множественные исполнители через запятую
  - [ ] Создатель записи указан правильно
- [ ] **5.3** Проверить работу фильтров в `/history`
- [ ] **5.4** Проверить генерацию отчетов в `/report`
- [ ] **5.5** Убедиться, что данные сохраняются в PostgreSQL
- [ ] **5.6** Проверить обработку ошибок (временно отключить n8n)

**✅ Результат этапа 5:** Система полностью функциональна

---

## 🔧 Переменные окружения

### Обязательные переменные для интеграции:

```bash
# n8n Integration
N8N_WEBHOOK_URL=https://your-n8n-instance.com/webhook/work-journal
N8N_WEBHOOK_SECRET=your_optional_secret_key

# Google Sheets Configuration  
GOOGLE_SHEETS_ID=1ABC123-example-google-sheets-id-XYZ789
```

### Как получить эти значения:

1. **N8N_WEBHOOK_URL**: 
   - Скопировать из настроек Webhook node в n8n
   - Формат: `https://your-domain.com/webhook/work-journal`

2. **GOOGLE_SHEETS_ID**:
   - Из URL Google Sheets: `https://docs.google.com/spreadsheets/d/[ЭТО_ID]/edit`

---

## 🧪 Команды для тестирования

### Тестирование n8n webhook:
```bash
# Через Python скрипт
python test_n8n_integration.py https://your-n8n.com/webhook/work-journal

# Через curl
curl -X POST https://your-n8n.com/webhook/work-journal \
  -H "Content-Type: application/json" \
  -d '{
    "source": "telegram_bot",
    "event_type": "work_journal_entry",
    "data": {
      "work_entry": {
        "date": "2025-08-01",
        "company": "Тест",
        "duration": "30 мин",
        "description": "Тестовая запись",
        "is_travel": false,
        "workers": ["Тимофей"],
        "workers_count": 1
      },
      "creator": {
        "name": "TestUser",
        "telegram_id": 123456789
      }
    }
  }'
```

### Тестирование Telegram Bot:
```bash
# Запуск бота
make dev

# Проверка логов
make logs-bot | grep "n8n"

# В Telegram:
/journal  # Создать запись
/history  # Проверить историю  
/report   # Проверить отчеты
```

---

## 🚨 Решение проблем

### Частые ошибки и решения:

#### ❌ "Webhook не отвечает"
- [ ] Проверить, что workflow активирован в n8n
- [ ] Проверить правильность URL в `.env`
- [ ] Проверить доступность n8n сервера

#### ❌ "Google Sheets API ошибка"
- [ ] Проверить права Service Account на таблицу
- [ ] Проверить правильность Document ID
- [ ] Убедиться, что Google Sheets API включен

#### ❌ "Данные не появляются в таблице"
- [ ] Проверить маппинг столбцов в n8n
- [ ] Проверить формат данных в Code node
- [ ] Посмотреть логи выполнения workflow

#### ❌ "Ошибка аутентификации"
- [ ] Перезагрузить Service Account credentials в n8n
- [ ] Проверить целостность JSON ключа
- [ ] Убедиться, что Service Account имеет нужные права

---

## 📊 Ожидаемый результат

После прохождения всех пунктов checklist:

✅ **Пользователь создает запись в Telegram** → данные сохраняются в PostgreSQL
✅ **Автоматически отправляется webhook в n8n** → данные обрабатываются
✅ **n8n добавляет запись в Google Sheets** → данные доступны для анализа
✅ **Система работает надежно** с обработкой ошибок

### Пример записи в Google Sheets:
```
2025-08-01T15:30:45Z | 2025-08-01 | Ива | 45 мин | Настройка сервера... | Нет | Тимофей, Дима | 2 | Kostya | 28795547 | kostya@example.com
```

---

## 🎯 Статус готовности

- [ ] ⬜ Все пункты checklist выполнены
- [ ] ⬜ Тестирование прошло успешно  
- [ ] ⬜ Интеграция работает стабильно
- [ ] ⬜ Документация обновлена

**✅ Когда все пункты отмечены - интеграция готова к производственному использованию!**
