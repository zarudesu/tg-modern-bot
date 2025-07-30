# Makefile для удобной разработки Telegram бота

.PHONY: help install dev-install test clean build up down logs shell db-shell

# Показать помощь
help:
	@echo "🤖 Modern Telegram Bot - Команды разработки"
	@echo ""
	@echo "Команды:"
	@echo "  install      - Установить зависимости в venv"
	@echo "  dev-install  - Установить зависимости для разработки"
	@echo "  test         - Запустить тесты"
	@echo "  clean        - Очистить временные файлы"
	@echo "  build        - Собрать Docker образы"
	@echo "  up          - Запустить все сервисы"
	@echo "  down        - Остановить все сервисы"
	@echo "  logs        - Показать логи бота"
	@echo "  shell       - Войти в контейнер бота"
	@echo "  db-shell    - Войти в PostgreSQL"

# Установка зависимостей
install:
	python3 -m venv venv
	./venv/bin/pip install -r requirements.txt

# Установка зависимостей для разработки
dev-install: install
	./venv/bin/pip install black flake8 mypy pytest pytest-asyncio

# Запуск тестов
test:
	python3 test_basic.py

# Очистка временных файлов
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
	find . -name "*.pyd" -delete
	find . -name ".coverage" -delete
	find . -name "*.cover" -delete
	find . -name "*.log" -delete

# Сборка Docker образов
build:
	docker-compose build

# Запуск всех сервисов
up:
	docker-compose up -d

# Остановка всех сервисов
down:
	docker-compose down

# Показать логи бота
logs:
	docker-compose logs -f telegram-bot

# Войти в контейнер бота
shell:
	docker-compose exec telegram-bot bash

# Войти в PostgreSQL
db-shell:
	docker-compose exec postgres psql -U bot_user -d telegram_bot

# Форматирование кода
format:
	./venv/bin/black app/
	./venv/bin/flake8 app/

# Проверка типов
typecheck:
	./venv/bin/mypy app/

# Полная проверка
check: format typecheck test
	@echo "✅ Все проверки пройдены!"
