#!/bin/bash

# Скрипт для быстрого обновления токена во всех .env файлах

echo "🔑 Обновление токена бота во всех конфигурационных файлах"
echo "========================================================="

# Запрашиваем новый токен
read -p "📝 Введите новый TELEGRAM_TOKEN (формат: 123456789:ABC...): " NEW_TOKEN

# Проверяем формат токена
if [[ ! $NEW_TOKEN =~ ^[0-9]+:[A-Za-z0-9_-]+$ ]]; then
    echo "❌ Неверный формат токена! Формат должен быть: 123456789:ABC..."
    exit 1
fi

echo "🔄 Обновляем токен в файлах..."

# Обновляем .env
if [ -f ".env" ]; then
    sed -i.bak "s/TELEGRAM_TOKEN=.*/TELEGRAM_TOKEN=$NEW_TOKEN/" .env
    echo "  ✅ .env обновлен"
else
    echo "  ❌ .env не найден"
fi

# Обновляем .env.dev
if [ -f ".env.dev" ]; then
    sed -i.bak "s/TELEGRAM_TOKEN=.*/TELEGRAM_TOKEN=$NEW_TOKEN/" .env.dev
    echo "  ✅ .env.dev обновлен"
else
    echo "  ❌ .env.dev не найден"
fi

# Обновляем .env.prod
if [ -f ".env.prod" ]; then
    sed -i.bak "s/TELEGRAM_TOKEN=.*/TELEGRAM_TOKEN=$NEW_TOKEN/" .env.prod
    echo "  ✅ .env.prod обновлен"
else
    echo "  ❌ .env.prod не найден"
fi

# Удаляем бэкапы
rm -f .env.bak .env.dev.bak .env.prod.bak

echo "✅ Токен обновлен во всех файлах!"
echo ""
echo "🚀 Теперь можно запустить бота:"
echo "   make dev"
