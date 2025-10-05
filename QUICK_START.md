# 🚀 Быстрый старт

## Минимальная настройка (5 минут)

### 1. Подготовка
```bash
git clone <repository-url>
cd tg-mordern-bot
cp .env.example .env
```

### 2. Заполнить .env
```env
# ОБЯЗАТЕЛЬНО
TELEGRAM_TOKEN=ваш_токен_бота
ADMIN_USER_ID=ваш_telegram_id

# БД (по умолчанию подходит)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/telegram_bot
REDIS_URL=redis://localhost:6379
```

### 3. Запуск
```bash
make dev  # Запустится БД + бот
```

### 4. Проверка
- Отправить `/start` боту
- Проверить логи: `make bot-logs`

## Дополнительные интеграции

### Plane.so (опционально)
```env
PLANE_API_URL=https://ваш-instance.plane.so
PLANE_API_TOKEN=ваш_токен
PLANE_WORKSPACE_SLUG=ваш_workspace
```

### n8n webhook (опционально)
```env
N8N_WEBHOOK_URL=https://ваш-n8n.com/webhook/work-journal
```

## Команды управления

```bash
make dev          # Старт
make dev-restart  # Перезапуск
make dev-stop     # Стоп
make bot-logs     # Логи
make status       # Статус
```

## Готово! 🎉

Бот работает и готов к использованию.
