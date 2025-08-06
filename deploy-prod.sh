#!/bin/bash

# Production Deployment Script for HHIVP IT Assistant
# Развертывание бота в production среде

set -e

echo "🚀 Развертывание HHIVP IT Assistant в Production..."

# Проверяем, что находимся в правильной директории
if [ ! -f "docker-compose.prod.yml" ]; then
    echo "❌ Ошибка: docker-compose.prod.yml не найден. Запустите скрипт из корня проекта."
    exit 1
fi

# Проверяем наличие .env.prod файла
if [ ! -f ".env.prod" ]; then
    echo "❌ Ошибка: .env.prod файл не найден."
    echo "📝 Создайте .env.prod файл на основе .env.example"
    exit 1
fi

# Останавливаем старые контейнеры
echo "🛑 Остановка старых контейнеров..."
docker-compose -f docker-compose.prod.yml down

# Создаем бэкап базы данных (если она существует)
echo "💾 Создание бэкапа базы данных..."
mkdir -p backups
BACKUP_FILE="backups/backup_$(date +%Y%m%d_%H%M%S).sql"
docker exec hhivp-bot-postgres-prod pg_dump -U hhivp_bot hhivp_bot_prod > "$BACKUP_FILE" 2>/dev/null || echo "ℹ️ База данных еще не существует, пропускаем бэкап"

# Собираем Docker образы
echo "🔨 Сборка Docker образов..."
docker-compose -f docker-compose.prod.yml build --no-cache

# Запускаем сервисы
echo "🚀 Запуск production сервисов..."
docker-compose -f docker-compose.prod.yml up -d

# Ждем запуска сервисов
echo "⏳ Ожидание запуска сервисов..."
sleep 30

# Проверяем статус сервисов
echo "🔍 Проверка статуса сервисов..."
docker-compose -f docker-compose.prod.yml ps

# Проверяем логи бота
echo "📋 Последние логи бота:"
docker-compose -f docker-compose.prod.yml logs --tail=20 bot

echo "✅ Развертывание завершено!"
echo ""
echo "🔗 Полезные команды:"
echo "  📊 Статус:      docker-compose -f docker-compose.prod.yml ps"
echo "  📋 Логи:        docker-compose -f docker-compose.prod.yml logs -f bot"
echo "  🛑 Остановка:   docker-compose -f docker-compose.prod.yml down"
echo "  🔄 Перезапуск:  docker-compose -f docker-compose.prod.yml restart bot"
echo ""
echo "🤖 Бот должен быть доступен в Telegram: @hhivp_it_bot"
