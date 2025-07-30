# Makefile для независимой разработки Telegram бота

.PHONY: help install dev-install test clean build
.PHONY: db-up db-down db-logs db-shell db-backup db-restore
.PHONY: bot-up bot-down bot-logs bot-shell
.PHONY: full-up full-down full-logs full-clean

# Показать помощь
help:
	@echo "🤖 Modern Telegram Bot - Команды независимой разработки"
	@echo ""
	@echo "📦 Установка и разработка:"
	@echo "  install      - Установить зависимости в venv"
	@echo "  dev-install  - Установить зависимости для разработки"
	@echo "  test         - Запустить тесты"
	@echo "  clean        - Очистить временные файлы"
	@echo ""
	@echo "🗄️ Управление базой данных (независимо):"
	@echo "  db-up        - Запустить только БД (PostgreSQL + Redis)"
	@echo "  db-down      - Остановить БД"
	@echo "  db-logs      - Показать логи БД"
	@echo "  db-shell     - Войти в PostgreSQL"
	@echo "  db-backup    - Создать бэкап БД"
	@echo "  db-restore   - Восстановить БД из бэкапа"
	@echo "  db-admin     - Запустить pgAdmin (веб-интерфейс)"
	@echo ""
	@echo "🤖 Управление ботом (независимо):"
	@echo "  bot-up       - Запустить только бота (подключится к БД)"
	@echo "  bot-down     - Остановить бота"
	@echo "  bot-logs     - Показать логи бота"
	@echo "  bot-shell    - Войти в контейнер бота"
	@echo "  bot-dev      - Запустить бота в режиме разработки"
	@echo ""
	@echo "🚀 Полный стек:"
	@echo "  full-up      - Запустить всё (БД + бот)"
	@echo "  full-down    - Остановить всё"
	@echo "  full-logs    - Показать логи всего стека"
	@echo "  full-clean   - Полная очистка (удалить все данные)"

# =====================================
# Установка и разработка
# =====================================

install:
	python3 -m venv venv
	./venv/bin/pip install -r requirements.txt

dev-install: install
	./venv/bin/pip install black flake8 mypy pytest pytest-asyncio

test:
	python3 test_basic.py

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
	find . -name "*.pyd" -delete
	find . -name ".coverage" -delete
	find . -name "*.cover" -delete
	find . -name "*.log" -delete

# =====================================
# Управление базой данных (независимо)
# =====================================

db-up:
	@echo "🗄️ Запускаем базу данных..."
	docker-compose -f docker-compose.database.yml up -d postgres redis
	@echo "✅ База данных запущена!"
	@echo "🔗 PostgreSQL: localhost:5432"
	@echo "🔗 Redis: localhost:6379"

db-down:
	@echo "🛑 Останавливаем базу данных..."
	docker-compose -f docker-compose.database.yml down

db-logs:
	docker-compose -f docker-compose.database.yml logs -f postgres redis

db-shell:
	docker-compose -f docker-compose.database.yml exec postgres psql -U bot_user -d telegram_bot

db-admin:
	@echo "🌐 Запускаем pgAdmin..."
	docker-compose -f docker-compose.database.yml --profile admin up -d pgadmin
	@echo "✅ pgAdmin доступен по адресу: http://localhost:8080"
	@echo "📧 Email: admin@example.com"
	@echo "🔑 Password: admin_password_2024"

db-backup:
	@echo "💾 Создаем бэкап базы данных..."
	mkdir -p backups
	docker-compose -f docker-compose.database.yml exec postgres pg_dump -U bot_user -d telegram_bot | gzip > backups/backup_$(shell date +%Y%m%d_%H%M%S).sql.gz
	@echo "✅ Бэкап создан в папке backups/"

db-restore:
	@echo "⚠️  Восстановление БД из последнего бэкапа..."
	@if [ -z "$(BACKUP_FILE)" ]; then \
		echo "❌ Укажите файл бэкапа: make db-restore BACKUP_FILE=backups/backup_20240101_120000.sql.gz"; \
		exit 1; \
	fi
	gunzip -c $(BACKUP_FILE) | docker-compose -f docker-compose.database.yml exec -T postgres psql -U bot_user -d telegram_bot

# =====================================
# Управление ботом (независимо)
# =====================================

bot-up:
	@echo "🤖 Запускаем Telegram бота..."
	@echo "⚠️  Убедитесь, что база данных запущена: make db-up"
	docker-compose -f docker-compose.bot.yml up -d
	@echo "✅ Бот запущен!"

bot-down:
	@echo "🛑 Останавливаем бота..."
	docker-compose -f docker-compose.bot.yml down

bot-logs:
	docker-compose -f docker-compose.bot.yml logs -f telegram-bot

bot-shell:
	docker-compose -f docker-compose.bot.yml exec telegram-bot bash

bot-dev:
	@echo "🔧 Запускаем бота в режиме разработки..."
	@if [ ! -f ".env.dev" ]; then \
		echo "❌ Создайте .env.dev файл для разработки"; \
		exit 1; \
	fi
	cp .env.dev .env
	./venv/bin/python -m app.main

# =====================================
# Полный стек
# =====================================

full-up:
	@echo "🚀 Запускаем полный стек..."
	docker-compose up -d
	@echo "✅ Полный стек запущен!"

full-down:
	@echo "🛑 Останавливаем полный стек..."
	docker-compose down

full-logs:
	docker-compose logs -f

full-clean:
	@echo "⚠️  ВНИМАНИЕ: Это удалит ВСЕ данные!"
	@read -p "Вы уверены? [y/N] " confirm && [ "$$confirm" = "y" ]
	docker-compose down -v
	docker-compose -f docker-compose.database.yml down -v
	docker-compose -f docker-compose.bot.yml down -v
	docker system prune -f
	@echo "✅ Полная очистка завершена"

# =====================================
# Разработка и проверки
# =====================================

format:
	./venv/bin/black app/
	./venv/bin/flake8 app/ --max-line-length=100

typecheck:
	./venv/bin/mypy app/ --ignore-missing-imports

check: format typecheck test
	@echo "✅ Все проверки пройдены!"

# =====================================
# Быстрые команды для ежедневной работы
# =====================================

dev: db-up bot-dev    # Быстрый старт разработки

dev-stop: db-down     # Быстрая остановка разработки

dev-restart: dev-stop dev  # Быстрый перезапуск

status:               # Показать статус всех контейнеров
	@echo "📊 Статус контейнеров:"
	@docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" --filter "name=telegram-bot"
