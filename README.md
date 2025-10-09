# 🤖 HHIVP IT Assistant Bot

Модульный Telegram бот для управления ежедневными задачами и журналом работ.

## 🚀 Быстрый старт

```bash
# 1. Клонировать репозиторий
git clone <repository-url>
cd tg-mordern-bot

# 2. Настроить окружение
cp .env.example .env
# Заполнить TELEGRAM_TOKEN и другие настройки

# 3. Запустить
make dev
```

## 📋 Основные команды

```bash
make dev          # 🚀 Запуск разработки
make dev-restart  # ⚡ Перезапуск
make dev-stop     # 🛑 Остановка

make bot-logs     # 📝 Логи бота
make db-shell     # 💻 PostgreSQL консоль
make test         # 🧪 Тесты
```

## 🏗️ Архитектура

### Модульная структура (ПОСЛЕ РЕФАКТОРИНГА):
```
app/
├── modules/                # 🎯 ГЛАВНЫЕ МОДУЛИ (основная разработка)
│   ├── daily_tasks/        # ✅ Email админов → Plane API
│   ├── task_reports/       # ✅ Автоматические отчеты о задачах
│   ├── work_journal/       # ✅ Журнал с фильтрами состояний
│   └── your_module/        # 🆕 Новые модули добавлять здесь
├── handlers/               # 🔧 Общие обработчики (start, help)
├── handlers/archive/       # 📦 Старые handlers (не используются)
├── services/               # 💼 Бизнес-логика
├── database/               # 🗄️ Модели БД
└── middleware/             # 🔧 Промежуточное ПО
```

**🎯 Принципы модульной архитектуры:**
- **Изоляция модулей** через фильтры
- **Приоритеты**: email → daily_tasks, активные состояния → work_journal
- **Новые фичи** создавать в `app/modules/your_module/`

### Порядок загрузки модулей:
1. **Common** - базовая функциональность
2. **Daily Tasks** - высший приоритет (email обработка)
3. **Task Reports** - автоматические отчеты о задачах из Plane
4. **Work Journal** - фильтры состояний

## ⚙️ Конфигурация

### Обязательные переменные (.env):
```env
TELEGRAM_TOKEN=your_bot_token
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/dbname
ADMIN_USER_ID=123456789
```

### Опциональные настройки:
```env
# Daily Tasks
PLANE_API_URL=https://your-plane-instance.com
PLANE_API_TOKEN=your_plane_token
PLANE_WORKSPACE_SLUG=your-workspace

# Дополнительные
REDIS_URL=redis://localhost:6379
LOG_LEVEL=INFO
```

## 🎯 Функциональность

### Daily Tasks:
- ✅ Email обработка для получения задач
- ✅ Интеграция с Plane.so
- ✅ Автоматические уведомления
- ✅ Фильтрация по проектам

### Task Reports:
- ✅ Автоматическое создание отчетов при закрытии задач в Plane
- ✅ Webhook интеграция с n8n
- ✅ Автозаполнение данных из Plane (название, описание, комментарии, исполнители)
- ✅ Маппинг компаний (HarzLabs → Харц Лабз и др.)
- ✅ Независимое редактирование полей
- ✅ Preview button flow
- ✅ Интеграция с Google Sheets и уведомлениями в группу

📚 **Документация:** [docs/TASK_REPORTS_FLOW.md](docs/TASK_REPORTS_FLOW.md)

### Work Journal:
- ✅ Создание записей о работе
- ✅ Управление компаниями и исполнителями
- ✅ История и отчеты
- ✅ Интеграция с n8n

### Команды бота:
```
/start    - Приветствие и справка
/journal  - Создать запись в журнале
/history  - История работ
/report   - Отчеты
/settings - Настройки (админы)
```

## 🧪 Тестирование

```bash
# Базовые тесты
python test_basic.py

# Тесты модулей
python test_work_journal.py
python test_plane_daily_tasks.py

# Все тесты
make test
```

## 🔧 Разработка

### Добавление нового модуля:

1. **Создать структуру:**
```
app/modules/new_module/
├── __init__.py
├── router.py          # Главный роутер
├── handlers.py        # Команды
├── filters.py         # Фильтры
└── callbacks.py       # Callback обработчики
```

2. **Подключить в main.py:**
```python
from .modules.new_module import router as new_module_router
dp.include_router(new_module_router)
```

3. **Использовать фильтры для изоляции:**
```python
@router.message(F.text, YourCustomFilter())
async def handle_text(message: Message):
    pass
```

### Структура фильтров:
```python
class YourCustomFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        # Логика фильтра
        return True
```

## 📦 Развертывание

### Docker (рекомендуемый):
```bash
# Производство
docker-compose -f docker-compose.prod.yml up -d

# Разработка
docker-compose up -d
```

### Системный сервис:
```bash
sudo cp hhivp-it-bot.service /etc/systemd/system/
sudo systemctl enable hhivp-it-bot
sudo systemctl start hhivp-it-bot
```

## 🔐 Безопасность

- ✅ Переменные окружения для секретов
- ✅ Фильтрация по ролям (админы/пользователи)
- ✅ Валидация всех входных данных
- ✅ Логирование без чувствительных данных

## 🐛 Отладка

### Логи:
```bash
make bot-logs          # Логи бота
make db-logs           # Логи БД
docker logs container  # Логи контейнера
```

### Частые проблемы:

**Бот не отвечает:**
```bash
make bot-logs  # Проверить логи
make status    # Статус сервисов
```

**БД не подключается:**
```bash
make db-up     # Запустить БД
make db-shell  # Проверить подключение
```

**Модули конфликтуют:**
- Проверить порядок загрузки в main.py
- Убедиться что фильтры изолированы
- Проверить приоритет роутеров

## 📚 API

### Work Journal Service:
```python
service = WorkJournalService(session)
await service.create_work_entry(...)
entries = await service.get_work_entries(user_id)
```

### Daily Tasks Service:
```python
service = DailyTasksService()
await service.process_email(email_text)
tasks = await service.get_user_tasks(user_id)
```

## 🤝 Вклад в разработку

1. Fork репозиторий
2. Создать feature branch
3. Следовать модульной архитектуре
4. Добавить тесты
5. Создать Pull Request

## 📄 Лицензия

MIT License - см. файл LICENSE
