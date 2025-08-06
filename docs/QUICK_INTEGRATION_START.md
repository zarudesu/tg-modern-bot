# ⚡ БЫСТРЫЙ СТАРТ ИНТЕГРАЦИИ N8N И GOOGLE SHEETS

## 🎯 Цель: Настроить автоматическую отправку записей из Telegram в Google Sheets через n8n

---

## 📋 Краткий план (2-4 часа)

### **Шаг 1: Google Sheets + Service Account (30-60 мин)**
1. Создать Google Sheets "HHIVP IT - Журнал работ"
2. Добавить заголовки: `Timestamp | Date | Company | Duration | Description | Travel | Workers | Workers_Count | Creator | Creator_ID`
3. Скопировать ID таблицы из URL
4. В Google Cloud Console:
   - Включить Google Sheets API
   - Создать Service Account
   - Скачать JSON ключ
   - Дать права Editor на таблицу

### **Шаг 2: n8n Workflow (30-60 мин)**
1. Открыть n8n → создать новый workflow
2. Импортировать `docs/n8n-workflow-template.json`
3. Настроить Google Sheets node:
   - Добавить Service Account credentials
   - Указать Document ID
4. Активировать workflow
5. Скопировать Webhook URL

### **Шаг 3: Telegram Bot (10 мин)**
1. Обновить `.env`:
   ```bash
   N8N_WEBHOOK_URL=https://your-n8n.com/webhook/work-journal
   GOOGLE_SHEETS_ID=your_sheets_id
   ```
2. Перезапустить: `make dev`

### **Шаг 4: Тестирование (30-60 мин)**
1. Запустить: `python test_n8n_integration.py <WEBHOOK_URL>`
2. Протестировать в Telegram: `/journal`
3. Проверить запись в Google Sheets

---

## 🔗 Полная документация

- **📖 Подробное руководство**: [N8N_GOOGLE_SHEETS_INTEGRATION_GUIDE.md](./N8N_GOOGLE_SHEETS_INTEGRATION_GUIDE.md)
- **✅ Пошаговый checklist**: [INTEGRATION_CHECKLIST.md](./INTEGRATION_CHECKLIST.md)
- **📊 Обзор интеграции**: [INTEGRATION_DOCUMENTATION_SUMMARY.md](./INTEGRATION_DOCUMENTATION_SUMMARY.md)

---

## 🧪 Быстрое тестирование

```bash
# 1. Тест webhook
python test_n8n_integration.py https://your-n8n.com/webhook/work-journal

# 2. Тест через Telegram
# Отправить /journal боту @hhivp_it_bot

# 3. Проверить Google Sheets
# Должна появиться новая запись
```

---

## ✅ Успешный результат

**После настройки пользователь создает запись в Telegram → автоматически появляется в Google Sheets**

**🎉 Интеграция готова к использованию!**
