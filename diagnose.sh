#!/bin/bash

# 🔍 Диагностика проблем деплоя HHIVP IT Assistant Bot

echo "🔍 ДИАГНОСТИКА HHIVP IT ASSISTANT BOT"
echo "===================================="

# 1. Проверка окружения
echo "📋 1. Проверка окружения:"
echo "  - Python версия: $(python3 --version 2>/dev/null || echo 'Не найден')"
echo "  - Docker версия: $(docker --version 2>/dev/null || echo 'Не найден')"
echo "  - Docker Compose версия: $(docker-compose --version 2>/dev/null || echo 'Не найден')"
echo ""

# 2. Проверка файлов конфигурации
echo "📁 2. Проверка файлов конфигурации:"
files=(".env" ".env.dev" ".env.prod" "requirements.txt" "Dockerfile")
for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✅ $file - найден"
    else
        echo "  ❌ $file - НЕ НАЙДЕН"
    fi
done
echo ""

# 3. Проверка Docker контейнеров
echo "🐳 3. Статус Docker контейнеров:"
if command -v docker &> /dev/null; then
    echo "  Запущенные контейнеры:"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(telegram|bot|postgres|redis)" || echo "    Нет запущенных контейнеров"
    echo ""
    echo "  Все контейнеры проекта:"
    docker ps -a --format "table {{.Names}}\t{{.Status}}" | grep -E "(telegram|bot|postgres|redis)" || echo "    Нет контейнеров проекта"
else
    echo "  ❌ Docker не установлен"
fi
echo ""

# 4. Проверка портов
echo "🔌 4. Проверка портов:"
ports=(5432 6379 8080)
for port in "${ports[@]}"; do
    if lsof -i :$port &> /dev/null; then
        echo "  🟢 Порт $port: ЗАНЯТ"
    else
        echo "  🔴 Порт $port: СВОБОДЕН"
    fi
done
echo ""

# 5. Проверка логов
echo "📋 5. Проверка логов:"
if [ -d "logs" ]; then
    echo "  📁 Директория logs найдена:"
    ls -la logs/ | head -5
    echo ""
    if [ -f "logs/bot.log" ]; then
        echo "  📄 Последние строки bot.log:"
        tail -3 logs/bot.log 2>/dev/null || echo "    Файл пустой или недоступен"
    fi
else
    echo "  ❌ Директория logs не найдена"
fi
echo ""

# 6. Проверка переменных окружения (без показа секретов)
echo "🔐 6. Проверка переменных окружения (.env):"
if [ -f ".env" ]; then
    echo "  ✅ .env файл найден"
    if grep -q "TELEGRAM_TOKEN=" .env; then
        token_length=$(grep "TELEGRAM_TOKEN=" .env | cut -d'=' -f2 | tr -d ' ' | wc -c)
        echo "  📝 TELEGRAM_TOKEN: длина $token_length символов"
    else
        echo "  ❌ TELEGRAM_TOKEN не найден"
    fi
    
    if grep -q "DATABASE_URL=" .env; then
        echo "  ✅ DATABASE_URL настроен"
    else
        echo "  ❌ DATABASE_URL не найден"
    fi
else
    echo "  ❌ .env файл не найден"
fi
echo ""

# 7. Тест подключения к базе данных
echo "🗄️ 7. Тест подключения к базе данных:"
if docker ps | grep -q postgres; then
    echo "  ✅ PostgreSQL контейнер запущен"
    if docker exec -it telegram-bot-postgres psql -U bot_user -d telegram_bot -c "SELECT 1;" &> /dev/null; then
        echo "  ✅ Подключение к базе работает"
    else
        echo "  ❌ Ошибка подключения к базе"
    fi
else
    echo "  ❌ PostgreSQL контейнер не запущен"
fi
echo ""

# 8. Рекомендации
echo "💡 8. Рекомендации по исправлению:"
echo "  1. Если токен не авторизован:"
echo "     - Идите к @BotFather в Telegram"
echo "     - /mybots → выберите бота → API Token → Revoke current token"
echo "     - Скопируйте новый токен в .env файлы"
echo ""
echo "  2. Для перезапуска:"
echo "     make dev-stop && make dev"
echo ""
echo "  3. Для полной очистки и перезапуска:"
echo "     make full-clean && make dev"
echo ""
echo "✅ Диагностика завершена!"
