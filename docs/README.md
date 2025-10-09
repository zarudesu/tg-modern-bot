# 📚 Документация HHIVP IT Assistant Bot

Эта директория содержит подробную документацию по всем компонентам бота.

## 📋 Основные документы

### Модули
- **[guides/task-reports-guide.md](guides/task-reports-guide.md)** - 🆕 Complete Task Reports Module Guide (архитектура, тестирование, troubleshooting)
- **[TASK_REPORTS_FLOW.md](TASK_REPORTS_FLOW.md)** - Полное описание модуля Task Reports (автоматические отчеты о задачах из Plane)
- **[DAILY_TASKS_SETUP.md](DAILY_TASKS_SETUP.md)** - Настройка Daily Tasks (email → Plane интеграция)

### Интеграции
- **[N8N_TASK_REPORTS_WORKFLOW.md](N8N_TASK_REPORTS_WORKFLOW.md)** - Workflow n8n для Task Reports (webhook → Telegram Bot)
- **[N8N_GOOGLE_SHEETS_INTEGRATION_GUIDE.md](N8N_GOOGLE_SHEETS_INTEGRATION_GUIDE.md)** - Полное руководство по интеграции с Google Sheets
- **[GOOGLE_SHEETS_INTEGRATION_GUIDE.md](GOOGLE_SHEETS_INTEGRATION_GUIDE.md)** - Дополнительные детали Google Sheets
- **[N8N_QUICK_SETUP.md](N8N_QUICK_SETUP.md)** - Быстрая настройка n8n
- **[N8N_TASK_REPORTS_UPDATE.md](N8N_TASK_REPORTS_UPDATE.md)** - Обновление workflow для Task Reports

### Развертывание
- **[DEPLOYMENT_PRODUCTION.md](DEPLOYMENT_PRODUCTION.md)** - Production развертывание
- **[TECHNICAL_SPEC.md](TECHNICAL_SPEC.md)** - Техническая спецификация

## 🗂️ Архивная документация

Устаревшие документы по рефакторингу и старым версиям хранятся в `archive/`:

### Task Reports Refactoring (Октябрь 2025)
- `archive/task_reports_refactoring/REFACTORING_COMPLETE.md` - Завершение рефакторинга
- `archive/task_reports_refactoring/REFACTORING_SUMMARY.md` - Краткое описание изменений
- `archive/task_reports_refactoring/CURRENT_BUGS.md` - Баги, которые были исправлены
- `archive/task_reports_refactoring/TASK_REPORTS_PLAN.md` - План рефакторинга
- `archive/task_reports_refactoring/TASK_REPORTS_REFACTORING.md` - Детали рефакторинга
- `archive/task_reports_refactoring/TASK_REPORTS_CONTINUE.md` - Продолжение работы

### Другие архивы
- `archive/PLANE_DAILY_TASKS_READY.md` - Готовность Plane Daily Tasks
- `archive/DEPLOYMENT_GUIDE.md` - Старый deployment guide
- `archive/VPS_DEPLOYMENT_GUIDE.md` - VPS deployment
- `archive/PRODUCTION_DEPLOYMENT.md` - Production deployment (старая версия)

## 🎯 Быстрые ссылки

### Для разработки
1. [CLAUDE.md](../CLAUDE.md) - 🆕 Оптимизированные инструкции для Claude Code (с Table of Contents)
2. [guides/task-reports-guide.md](guides/task-reports-guide.md) - 🆕 Complete Task Reports Guide
3. [DEV_GUIDE.md](../DEV_GUIDE.md) - Руководство разработчика
4. [TASK_REPORTS_FLOW.md](TASK_REPORTS_FLOW.md) - Flow описание Task Reports

### Для деплоя
1. [DEPLOYMENT_PRODUCTION.md](DEPLOYMENT_PRODUCTION.md) - Production deployment
2. [QUICK_START.md](../QUICK_START.md) - Быстрый старт
3. [DEPLOYMENT.md](../DEPLOYMENT.md) - Общие инструкции по развертыванию

### Для тестирования
1. [TASK_REPORTS_FLOW.md](TASK_REPORTS_FLOW.md) - Testing checklist в конце документа
2. [TESTING_CHECKLIST.md](../TESTING_CHECKLIST.md) - Общий чеклист

## 🔄 История изменений

### 2025-10-08
- ✅ Завершен рефакторинг Task Reports (2129 → 11 файлов)
- ✅ Исправлены 5 критических багов
- ✅ Создана полная документация TASK_REPORTS_FLOW.md
- ✅ Архивированы устаревшие документы рефакторинга
- 🆕 Оптимизирован CLAUDE.md (730 → 682 строки):
  - Добавлен Table of Contents для быстрой навигации
  - Quick Start перемещен в начало
  - Создан Module Status Dashboard
  - Task Reports вынесен в отдельный гайд `guides/task-reports-guide.md`
  - Улучшена структура документа

### 2025-08-23
- ✅ Настроен Daily Tasks Setup
- ✅ Добавлена интеграция с Plane API

### 2025-08-06
- ✅ Создана техническая спецификация
- ✅ Настроена интеграция с Google Sheets через n8n
