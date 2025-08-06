#!/bin/bash

# Скрипт для чистого запуска бота без конфликтов

echo "🤖 Запуск HHIVP IT Assistant Bot (Development)"
echo "=========================================="

# Переходим в директорию проекта
cd "$(dirname "$0")"

# Убиваем все процессы бота для предотвращения конфликтов
echo "🔪 Остановка всех экземпляров бота..."
pkill -f "python.*app\.main" 2>/dev/null || true
pkill -f "app\.main" 2>/dev/null || true
pkill -f "hhivp" 2>/dev/null || true

# Ждем завершения процессов
sleep 2

# Проверяем что все процессы остановлены
if pgrep -f "app\.main" > /dev/null; then
    echo "❌ Найдены оставшиеся процессы бота:"
    ps aux | grep "app\.main" | grep -v grep
    echo "Убиваем принудительно..."
    pkill -9 -f "app\.main" 2>/dev/null || true
    sleep 1
fi

# Проверяем статус базы данных
echo "🗄️ Проверка базы данных..."
if ! docker ps | grep -q "telegram-bot-postgres"; then
    echo "❌ PostgreSQL не запущен. Запускаем..."
    make db-up
    sleep 3
fi

if ! docker ps | grep -q "telegram-bot-redis"; then
    echo "❌ Redis не запущен. Запускаем..."
    make db-up
    sleep 3
fi

echo "✅ База данных готова"

# Активируем виртуальное окружение и запускаем бота
echo "🚀 Запуск бота..."
echo "   Telegram: @hhivp_it_bot"
echo "   Режим: Development (локально)"
echo "   База данных: Docker (PostgreSQL + Redis)"
echo ""
echo "Для остановки нажмите Ctrl+C"
echo "=========================================="

# Запуск с активированным venv
source venv/bin/activate && python -m app.main
