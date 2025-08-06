#!/bin/bash

# 🚀 Быстрое исправление критической ошибки и деплой на VPS
# Исправляет SyntaxError в main.py и перезапускает бота

echo "🔧 ИСПРАВЛЕНИЕ КРИТИЧЕСКОЙ ОШИБКИ - SyntaxError в main.py"
echo "========================================================"

# Проверяем, что находимся в правильной директории
if [ ! -f "app/main.py" ]; then
    echo "❌ Ошибка: Запустите скрипт из корня проекта (где есть app/main.py)"
    exit 1
fi

echo "🔍 Исправляем SyntaxError в app/main.py..."

# Создаем бэкап
cp app/main.py app/main.py.backup
echo "💾 Создан бэкап: app/main.py.backup"

# Исправляем проблему с f-string и backslash
cat > /tmp/fix_main.py << 'EOF'
import re

# Читаем файл
with open('app/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Исправляем проблемные строки
old_pattern = '''        # Уведомляем всех администраторов о запуске
        from datetime import datetime
        current_time = datetime.now().strftime("%d\\.%m\\.%Y %H:%M:%S")
        
        startup_message = (
            "🟢 *HHIVP IT Assistant Bot запущен успешно\\!*\n\n"
            f"🤖 *Username:* @{bot_info.username.replace('_', '\\_')}\n"
            f"🆔 *Bot ID:* {bot_info.id}\n"
            f"📊 *Версия:* 1\\.1\\.0\n"
            f"🕐 *Время запуска:* {current_time}\n\n"
            f"🚀 *Готов к работе\\!* Используйте /start для начала\\."
        )'''

new_pattern = '''        # Уведомляем всех администраторов о запуске
        from datetime import datetime
        escaped_time = datetime.now().strftime("%d\\.%m\\.%Y %H:%M:%S")
        escaped_username = bot_info.username.replace('_', '\\_')
        
        startup_message = (
            "🟢 *HHIVP IT Assistant Bot запущен успешно\\!*\n\n"
            f"🤖 *Username:* @{escaped_username}\n"
            f"🆔 *Bot ID:* {bot_info.id}\n"
            f"📊 *Версия:* 1\\.1\\.0\n"
            f"🕐 *Время запуска:* {escaped_time}\n\n"
            f"🚀 *Готов к работе\\!* Используйте /start для начала\\."
        )'''

# Заменяем
content = content.replace(old_pattern, new_pattern)

# Записываем обратно
with open('app/main.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Исправление применено!")
EOF

python3 /tmp/fix_main.py
rm /tmp/fix_main.py

echo "✅ SyntaxError исправлена!"

# Проверяем синтаксис Python
echo "🔍 Проверяем синтаксис Python..."
if python3 -m py_compile app/main.py; then
    echo "✅ Синтаксис корректен!"
else
    echo "❌ Ошибка синтаксиса все еще присутствует!"
    echo "📝 Восстанавливаем из бэкапа..."
    cp app/main.py.backup app/main.py
    exit 1
fi

# Перезапускаем контейнеры
echo "🔄 Перезапускаем Docker контейнеры..."

# Останавливаем
docker-compose -f docker-compose.prod.yml down

# Пересобираем образ
echo "🔨 Пересборка Docker образа..."
docker-compose -f docker-compose.prod.yml build --no-cache bot

# Запускаем
echo "🚀 Запуск обновленного бота..."
docker-compose -f docker-compose.prod.yml up -d

# Ждем запуска
echo "⏳ Ожидание запуска сервисов..."
sleep 15

# Проверяем статус
echo "📊 Статус сервисов:"
docker-compose -f docker-compose.prod.yml ps

# Показываем логи
echo "📋 Последние логи бота:"
docker-compose -f docker-compose.prod.yml logs --tail=20 bot

echo ""
echo "✅ ИСПРАВЛЕНИЕ ЗАВЕРШЕНО!"
echo ""
echo "🔗 Полезные команды:"
echo "  📊 Статус:      docker-compose -f docker-compose.prod.yml ps"
echo "  📋 Логи:        docker-compose -f docker-compose.prod.yml logs -f bot"
echo "  🔄 Перезапуск:  docker-compose -f docker-compose.prod.yml restart bot"
