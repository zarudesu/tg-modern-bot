#!/bin/bash

# 🚀 Скрипт быстрой настройки для разработки Telegram бота

echo "🤖 Настройка окружения для разработки Telegram бота"
echo "=================================================="

# Проверяем Python
echo "🐍 Проверяем Python..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo "✅ Python найден: $PYTHON_VERSION"
else
    echo "❌ Python3 не найден! Установите Python 3.8+"
    exit 1
fi

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

# Проверяем .env файл
if [ ! -f ".env" ]; then
    echo "⚙️ Создаем .env файл из примера..."
    cp .env.example .env
    echo "⚠️  ВАЖНО: Отредактируйте .env файл со своими настройками!"
    echo "   - TELEGRAM_TOKEN (получите у @BotFather)"
    echo "   - ADMIN_USER_ID (ваш Telegram ID)"
    echo "   - DATABASE_URL (настройте PostgreSQL)"
else
    echo "✅ .env файл уже существует"
fi

# Создаем директорию для логов
mkdir -p logs
echo "✅ Директория logs создана"

echo ""
echo "🎉 Настройка завершена!"
echo ""
echo "📋 Следующие шаги:"
echo "   1. Отредактируйте .env файл: nano .env"
echo "   2. Получите токен бота: https://t.me/BotFather"
echo "   3. Узнайте свой Telegram ID: https://t.me/userinfobot"
echo "   4. Запустите тесты: python test_basic.py"
echo "   5. Или запустите с Docker: make up"
echo ""
echo "💡 Полезные команды:"
echo "   make help     - показать все команды"
echo "   make test     - запустить тесты"
echo "   make up       - запустить с Docker"
echo "   make logs     - посмотреть логи"
echo ""
