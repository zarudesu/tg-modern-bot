# 🐳 Docker Development Guide

## Почему код не обновляется после изменений?

**TL;DR:** Код находится ВНУТРИ Docker образа, а не монтируется как volume. После изменений нужно **пересобрать образ + пересоздать контейнер**.

---

## 🎯 Quick Reference

### После изменения Python кода:

```bash
# ✅ ПРАВИЛЬНО - используйте Makefile:
make bot-rebuild-clean        # Пересобрать только бот
make full-rebuild-clean       # Пересобрать полный стек

# ✅ ПРАВИЛЬНО - вручную:
docker-compose build --no-cache telegram-bot
docker-compose up -d --force-recreate telegram-bot
```

### ❌ НЕ РАБОТАЕТ:

```bash
docker-compose restart telegram-bot       # Перезапускает СТАРЫЙ контейнер
docker-compose build telegram-bot         # Собирает образ, но НЕ пересоздает контейнер
docker-compose up -d telegram-bot         # Использует существующий контейнер
```

---

## 📚 Полный Workflow

### Понимание архитектуры

В нашем проекте:
- **НЕ используется volume mount** для кода (только для логов и .env)
- Код **копируется В образ** при сборке (см. Dockerfile)
- Контейнер использует **фиксированную копию** кода из образа

```yaml
# docker-compose.yml
volumes:
  - ./logs:/app/logs        # ✅ Монтируется
  - ./.env:/app/.env:ro     # ✅ Монтируется
  # ❌ Код НЕ монтируется!
```

### 3-шаговый процесс обновления кода:

```bash
# Шаг 1: Изменить код локально
vim app/modules/task_reports/handlers/preview.py

# Шаг 2: Пересобрать Docker образ (БЕЗ кэша!)
docker-compose build --no-cache telegram-bot

# Шаг 3: Пересоздать контейнер из нового образа
docker-compose up -d --force-recreate telegram-bot
```

### Почему `--force-recreate`?

| Команда | Что делает | Обновляет код? |
|---------|-----------|----------------|
| `restart` | Останавливает и запускает СУЩЕСТВУЮЩИЙ контейнер | ❌ Нет |
| `up -d` | Создает контейнер, если его нет | ❌ Использует старый |
| `up -d --force-recreate` | УДАЛЯЕТ старый контейнер + создает новый | ✅ Да! |

---

## 🛠️ Makefile Команды

### Рекомендуется (проще и безопаснее)

```bash
# Пересборка только бота (БД уже запущена)
make bot-rebuild-clean

# Пересборка полного стека (БД + Redis + Bot)
make full-rebuild-clean

# Просмотр логов
make bot-logs
make full-logs

# Статус
make status
```

### Что делают команды под капотом:

```makefile
bot-rebuild-clean:
    docker-compose -f docker-compose.bot.yml build --no-cache
    docker-compose -f docker-compose.bot.yml up -d --force-recreate
```

---

## 🎓 Полезные Docker команды

### Проверка что код обновился:

```bash
# Проверить файл внутри контейнера
docker exec telegram-bot-app-full cat /app/app/modules/task_reports/handlers/preview.py | grep "map_workers"

# Проверить Python импорты
docker exec telegram-bot-app-full python -c "from app.modules.task_reports.utils import map_workers_to_display_names; print(map_workers_to_display_names(['zardes']))"
```

### Логи и отладка:

```bash
# Просмотр логов в реальном времени
docker-compose logs -f telegram-bot
docker logs telegram-bot-app-full -f

# Войти в контейнер
docker exec -it telegram-bot-app-full bash

# Список запущенных контейнеров
docker ps
```

### Полная очистка (когда все сломалось):

```bash
# Остановить все
docker-compose down

# Удалить образы
docker rmi telegram-bot-telegram-bot

# Пересобрать с нуля
docker-compose build --no-cache
docker-compose up -d --force-recreate
```

---

## 🔄 Сравнение: Local vs Docker

### Local Development (bot_manager.sh)

**Преимущества:**
- ✅ Код обновляется автоматически при изменении
- ✅ Быстрый перезапуск: `make dev-restart`
- ✅ Не нужно пересобирать образы

**Недостатки:**
- ❌ Нужен Python 3.11 локально
- ❌ Нужны все зависимости в venv

**Workflow:**
```bash
# Изменить код
vim app/handlers/start.py

# Перезапустить - ВСЁ!
make dev-restart
```

### Docker Development

**Преимущества:**
- ✅ Изолированная среда
- ✅ Не нужен Python локально
- ✅ Production-like окружение

**Недостатки:**
- ❌ Нужно пересобирать образ после изменений
- ❌ Медленнее при разработке

**Workflow:**
```bash
# Изменить код
vim app/handlers/start.py

# Пересобрать И пересоздать
make bot-rebuild-clean
```

---

## 🎯 Когда использовать что?

### Используйте `make bot-rebuild-clean`:
- ✅ После изменения Python кода
- ✅ После изменения зависимостей (requirements.txt)
- ✅ После изменения Dockerfile

### Достаточно `docker-compose restart`:
- ✅ Изменения только в .env
- ✅ Изменения в БД (не требуют перезапуска бота)

### Нужен `--force-recreate` но НЕ `--no-cache`:
- ✅ Изменения в docker-compose.yml (порты, volumes, env vars)

---

## 📝 Checklist после изменений

- [ ] Изменили Python код → `make bot-rebuild-clean`
- [ ] Изменили requirements.txt → `make bot-rebuild-clean`
- [ ] Изменили .env → `docker-compose restart telegram-bot`
- [ ] Изменили docker-compose.yml → `docker-compose up -d --force-recreate`
- [ ] Проверили логи → `make bot-logs`
- [ ] Протестировали в Telegram

---

## 🆘 Troubleshooting

### Проблема: "Код не обновился после изменений"

```bash
# Решение 1: Полная пересборка
make bot-rebuild-clean

# Решение 2: Вручную с проверкой
docker-compose build --no-cache telegram-bot
docker-compose up -d --force-recreate telegram-bot
docker logs telegram-bot-app-full --tail 50
```

### Проблема: "Контейнер не запускается"

```bash
# Проверить логи
docker logs telegram-bot-app-full

# Проверить статус
docker ps -a | grep telegram-bot

# Полная очистка + пересборка
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Проблема: "База данных не подключается"

```bash
# Запустить БД отдельно
make db-up

# Проверить сеть
docker network ls | grep telegram-bot

# Проверить подключение
docker exec telegram-bot-app-full ping postgres
```

---

## 🔗 Дополнительные ресурсы

- **Главная документация:** [CLAUDE.md](CLAUDE.md)
- **Makefile команды:** `make help`
- **Docker Compose docs:** https://docs.docker.com/compose/

---

**Last Updated:** 2025-10-09
**Author:** Claude Code + Human
