# 🔗 Руководство по настройке интеграции n8n и Google Sheets

## 🎯 Цель интеграции

Настроить автоматическую отправку записей из Telegram бота в Google Sheets через n8n:
**Telegram Bot → n8n Webhook → Google Sheets**

---

## 📋 Пошаговая настройка

### Этап 1: Подготовка Google Sheets

#### 1.1 Создание Google Sheets документа

1. **Создайте новую Google Sheets таблицу**:
   - Перейдите на [sheets.google.com](https://sheets.google.com)
   - Создайте новый документ
   - Назовите его "HHIVP IT - Журнал работ"

2. **Настройте структуру таблицы** (добавьте заголовки в первую строку):

| A | B | C | D | E | F | G | H | I | J |
|---|---|---|---|---|---|---|---|---|---|
| **Timestamp** | **Date** | **Company** | **Duration** | **Description** | **Travel** | **Workers** | **Workers_Count** | **Creator** | **Creator_ID** |

#### 1.2 Получение ID Google Sheets

1. **Скопируйте ID таблицы** из URL:
   ```
   https://docs.google.com/spreadsheets/d/[ЭТОТ_ID_НУЖЕН]/edit
   ```
   
2. **Сохраните ID** - он понадобится для n8n и переменных окружения

#### 1.3 Настройка Google Service Account

1. **Перейдите в Google Cloud Console**:
   - [console.cloud.google.com](https://console.cloud.google.com)
   - Создайте новый проект или выберите существующий

2. **Включите Google Sheets API**:
   - Перейдите в "APIs & Services" → "Library"
   - Найдите "Google Sheets API"
   - Нажмите "Enable"

3. **Создайте Service Account**:
   - Перейдите в "APIs & Services" → "Credentials"
   - Нажмите "Create Credentials" → "Service Account"
   - Заполните:
     - **Name**: `n8n-sheets-integration`
     - **Description**: `Service account for n8n Google Sheets integration`

4. **Создайте ключ для Service Account**:
   - Откройте созданный Service Account
   - Перейдите в "Keys" → "Add Key" → "Create new key"
   - Выберите формат **JSON**
   - Скачайте файл ключа (например, `service-account-key.json`)

5. **Предоставьте доступ к таблице**:
   - Откройте созданную Google Sheets таблицу
   - Нажмите "Share" в правом верхнем углу
   - Добавьте email Service Account (из скачанного JSON файла)
   - Установите права **"Editor"**

---

### Этап 2: Настройка n8n Workflow

#### 2.1 Создание нового Workflow

1. **Откройте n8n** и создайте новый workflow
2. **Назовите workflow**: `HHIVP-Telegram-to-Sheets`

#### 2.2 Добавление Webhook Node

1. **Добавьте Webhook node**:
   - Drag & Drop "Webhook" из Core Nodes
   - Настройте параметры:
     - **HTTP Method**: `POST`
     - **Path**: `work-journal`
     - **Authentication**: `Header Auth` (опционально)
     - **Response Mode**: `Respond to Webhook`

2. **Получите Webhook URL**:
   - После сохранения скопируйте **Webhook URL**
   - Например: `https://your-n8n-instance.com/webhook/work-journal`

#### 2.3 Добавление Data Transformation

1. **Добавьте Code node** после Webhook:
   ```javascript
   // Извлекаем данные из webhook
   const webhookData = items[0].json;
   
   // Проверяем структуру данных
   if (!webhookData.data || !webhookData.data.work_entry) {
     throw new Error('Invalid webhook data structure');
   }
   
   const workEntry = webhookData.data.work_entry;
   const creator = webhookData.data.creator;
   
   // Форматируем для Google Sheets
   const formattedData = {
     timestamp: new Date().toISOString(),
     date: workEntry.date,
     company: workEntry.company,
     duration: workEntry.duration,
     description: workEntry.description,
     travel: workEntry.is_travel ? 'Да' : 'Нет',
     workers: Array.isArray(workEntry.workers) ? workEntry.workers.join(', ') : workEntry.workers,
     workers_count: workEntry.workers_count || 1,
     creator: creator.name,
     creator_id: creator.telegram_id
   };
   
   return [{ json: formattedData }];
   ```

#### 2.4 Настройка Google Sheets Node

1. **Добавьте Google Sheets node**:
   - Выберите "Google Sheets" из App Nodes
   - **Operation**: `Append`

2. **Настройте аутентификацию**:
   - **Authentication**: `Service Account`
   - Загрузите скачанный JSON файл Service Account

3. **Настройте параметры**:
   - **Document ID**: Вставьте ID Google Sheets
   - **Sheet**: `Sheet1` (или название вашего листа)
   - **Range**: `A:J` (диапазон всех столбцов)
   - **Data Mode**: `Auto-map Input Data`

4. **Настройте маппинг данных**:
   ```
   Column A (Timestamp) → {{ $json.timestamp }}
   Column B (Date) → {{ $json.date }}
   Column C (Company) → {{ $json.company }}
   Column D (Duration) → {{ $json.duration }}
   Column E (Description) → {{ $json.description }}
   Column F (Travel) → {{ $json.travel }}
   Column G (Workers) → {{ $json.workers }}
   Column H (Workers_Count) → {{ $json.workers_count }}
   Column I (Creator) → {{ $json.creator }}
   Column J (Creator_ID) → {{ $json.creator_id }}
   ```

#### 2.5 Добавление Response Node

1. **Добавьте HTTP Response node**:
   ```json
   {
     "status": "success",
     "message": "Work journal entry added to Google Sheets",
     "timestamp": "{{ new Date().toISOString() }}"
   }
   ```

#### 2.6 Обработка ошибок

1. **Добавьте Error Trigger node**:
   - Подключите к основному workflow
   
2. **Добавьте HTTP Response node для ошибок**:
   ```json
   {
     "status": "error",
     "message": "Failed to process work journal entry",
     "error": "{{ $json.error }}",
     "timestamp": "{{ new Date().toISOString() }}"
   }
   ```

---

### Этап 3: Настройка Telegram Bot

#### 3.1 Обновление переменных окружения

1. **Откройте файл `.env`** в проекте:
   ```bash
   cd /Users/admin-user/Projects/tg-mordern-bot
   nano .env
   ```

2. **Добавьте переменные n8n интеграции**:
   ```bash
   # n8n Integration
   N8N_WEBHOOK_URL=https://your-n8n-instance.com/webhook/work-journal
   N8N_WEBHOOK_SECRET=your_optional_secret_key
   
   # Google Sheets Configuration
   GOOGLE_SHEETS_ID=your_google_sheets_id_here
   ```

#### 3.2 Проверка готовности бота

1. **Убедитесь, что бот запущен**:
   ```bash
   make dev
   # или
   make full-up
   ```

2. **Проверьте статус**:
   ```bash
   make status
   make logs-bot
   ```

---

### Этап 4: Тестирование интеграции

#### 4.1 Тест n8n Workflow

1. **Активируйте workflow** в n8n
2. **Проверьте Webhook URL** доступен
3. **Протестируйте через Postman** или curl:

   ```bash
   curl -X POST https://your-n8n-instance.com/webhook/work-journal \
     -H "Content-Type: application/json" \
     -d '{
       "source": "telegram_bot",
       "event_type": "work_journal_entry",
       "timestamp": "2025-08-01T15:30:00Z",
       "data": {
         "work_entry": {
           "date": "2025-08-01",
           "company": "Тестовая компания",
           "duration": "30 мин",
           "description": "Тестовое описание работ",
           "is_travel": false,
           "workers": ["Тимофей", "Дима"],
           "workers_count": 2
         },
         "creator": {
           "name": "TestUser",
           "telegram_id": 123456789
         }
       }
     }'
   ```

#### 4.2 Тест через Telegram Bot

1. **Откройте Telegram** и найдите бота @hhivp_it_bot
2. **Создайте тестовую запись**:
   ```
   /journal
   ```
3. **Заполните все поля** пошагово
4. **Подтвердите сохранение**

#### 4.3 Проверка результатов

1. **Проверьте Google Sheets** - должна появиться новая строка
2. **Проверьте логи n8n** - workflow должен выполниться успешно
3. **Проверьте логи бота**:
   ```bash
   make logs-bot | grep "n8n"
   ```

---

### Этап 5: Мониторинг и отладка

#### 5.1 Логирование в n8n

1. **Включите детальное логирование** в n8n
2. **Добавьте логирование в Code node**:
   ```javascript
   console.log('Received webhook data:', JSON.stringify(webhookData, null, 2));
   console.log('Formatted data for Sheets:', JSON.stringify(formattedData, null, 2));
   ```

#### 5.2 Мониторинг ошибок

1. **В Google Sheets проверяйте**:
   - Правильность форматирования данных
   - Наличие всех обязательных полей
   - Корректность дат и времени

2. **В n8n мониторьте**:
   - Статус выполнения workflow
   - Ошибки аутентификации Google Sheets
   - Проблемы с маппингом данных

3. **В Telegram Bot логах**:
   - Успешность отправки webhook
   - Ошибки HTTP запросов
   - Статусы ответов от n8n

#### 5.3 Резервное сохранение

Telegram бот уже сохраняет все записи в PostgreSQL, поэтому даже при сбоях n8n данные не потеряются.

---

## 🔧 Расширенные настройки

### Опциональные улучшения

#### 1. Аутентификация Webhook

1. **В n8n добавьте Header Authentication**:
   - Header Name: `X-API-Key`
   - Header Value: `your_secret_api_key`

2. **В Telegram Bot обновите отправку**:
   ```python
   headers = {
       "Content-Type": "application/json",
       "X-API-Key": settings.N8N_WEBHOOK_SECRET
   }
   ```

#### 2. Retry логика для надежности

Бот уже имеет встроенную retry логику в `N8nIntegrationService`.

#### 3. Уведомления об ошибках

1. **В n8n добавьте Slack/Email node** для уведомлений об ошибках
2. **Подключите к Error Trigger**

---

## 📊 Ожидаемый результат

После настройки интеграции:

1. **Пользователь создает запись** через `/journal` в Telegram
2. **Бот сохраняет в PostgreSQL** (основное хранилище)
3. **Бот отправляет webhook** в n8n
4. **n8n обрабатывает данные** и форматирует для Google Sheets
5. **Данные автоматически добавляются** в Google Sheets таблицу
6. **Пользователь получает подтверждение** в Telegram

### Пример результата в Google Sheets:

| Timestamp | Date | Company | Duration | Description | Travel | Workers | Workers_Count | Creator | Creator_ID |
|-----------|------|---------|----------|-------------|--------|---------|---------------|---------|------------|
| 2025-08-01T15:30:45Z | 2025-08-01 | Ива | 45 мин | Настройка сервера... | Нет | Тимофей, Дима | 2 | Kostya | YOUR_TELEGRAM_ID |

---

## 🎯 Заключение

После выполнения всех этапов вы получите:

- ✅ **Полностью автоматизированную** систему записи работ
- ✅ **Надежное дублирование** данных (PostgreSQL + Google Sheets)
- ✅ **Удобный интерфейс** через Telegram бот
- ✅ **Централизованное хранение** в Google Sheets для отчетности
- ✅ **Масштабируемую архитектуру** для добавления новых интеграций

**Интеграция готова к использованию!** 🚀
