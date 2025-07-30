#!/bin/bash

# 🚀 Скрипт настройки независимой разработки Telegram бота

echo "🤖 Настройка независимой разработки Telegram бота"
echo "==============================================="

# Проверяем Docker
echo "🐳 Проверяем Docker..."
if command -v docker &> /dev/null && command -v docker-compose &> /dev/null; then
    DOCKER_VERSION=$(docker --version)
    COMPOSE_VERSION=$(docker-compose --version)
    echo "✅ Docker найден: $DOCKER_VERSION"
    echo "✅ Docker Compose найден: $COMPOSE_VERSION"
else
    echo "❌ Docker или Docker Compose не найден!"
    echo "   Установите Docker Desktop: https://www.docker.com/products/docker-desktop"
    exit 1
fi

# Проверяем Python
echo "🐍 Проверяем Python..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo "✅ Python найден: $PYTHON_VERSION"
else
    echo "❌ Python3 не найден! Установите Python 3.8+"
    exit 1
fi

# Создаем необходимые директории
echo "📁 Создаем директории..."
mkdir -p logs
mkdir -p backups
mkdir -p sql/init
echo "✅ Директории созданы"

# Создаем виртуальное окружение если его нет
if [ ! -d "venv" ]; then
    echo "📦 Создаем виртуальное окружение..."
    python3 -m venv venv
    echo "✅ Виртуальное окружение создано"
else
    echo "✅ Виртуальное окружение уже существует"
fi

# Активируем и устанавливаем зависимости
echo "📥 Устанавливаем зависимости..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo "✅ Зависимости установлены"

# Настраиваем конфигурационные файлы
echo "⚙️ Настраиваем конфигурацию..."

# Создаем .env для разработки если его нет
if [ ! -f ".env" ]; then
    echo "📝 Создаем .env файл для разработки..."
    cp .env.dev .env
    echo "✅ .env файл создан"
else
    echo "✅ .env файл уже существует"
fi

# Создаем .env.dev если его нет
if [ ! -f ".env.dev" ]; then
    echo "📝 Создаем .env.dev файл..."
    cp .env.example .env.dev
    echo "✅ .env.dev файл создан"
fi

# Проверяем Docker сети
echo "🌐 Настраиваем Docker сети..."
if ! docker network ls | grep -q "telegram-bot-network"; then
    docker network create telegram-bot-network
    echo "✅ Docker сеть создана"
else
    echo "✅ Docker сеть уже существует"
fi

echo ""
echo "🎉 Настройка независимой разработки завершена!"
echo ""
echo "📋 Доступные режимы работы:"
echo ""
echo "1️⃣  НЕЗАВИСИМАЯ РАЗРАБОТКА (рекомендуется):"
echo "   make db-up        # Запустить только БД"
echo "   make bot-dev      # Запустить бота в режиме разработки"
echo "   make dev-stop     # Остановить всё"
echo ""
echo "2️⃣  DOCKER РАЗРАБОТКА:"
echo "   make db-up        # Запустить БД"
echo "   make bot-up       # Запустить бота в Docker"
echo ""
echo "3️⃣  ПОЛНЫЙ СТЕК:"
echo "   make full-up      # Запустить всё сразу"
echo ""
echo "🔧 Полезные команды:"
echo "   make help         # Показать все команды"
echo "   make status       # Статус контейнеров"
echo "   make db-shell     # PostgreSQL консоль"
echo "   make db-admin     # pgAdmin веб-интерфейс"
echo "   make test         # Запустить тесты"
echo ""
echo "⚠️  ВАЖНО: Настройте .env файл перед запуском:"
echo "   - TELEGRAM_TOKEN (получите у @BotFather)"
echo "   - ADMIN_USER_ID (ваш Telegram ID)"
echo ""
echo "🌟 Быстрый старт:"
echo "   1. nano .env                    # Настройте токены"
echo "   2. make dev                     # Запустить разработку"
echo "   3. Разрабатывайте бота локально!"
echo ""
