#!/bin/bash

# Скрипт для публикации проекта на GitHub
# Выполните после создания репозитория на GitHub.com

cd /Users/your-username/Projects/tg-mordern-bot

echo "🔗 Настройка remote origin..."
git remote set-url origin git@github.com:zarudesu/tg-modern-bot.git

echo "🚀 Публикация на GitHub..."
git push -u origin main

echo "✅ Проект успешно опубликован!"
echo "🌐 URL репозитория: https://github.com/zarudesu/tg-modern-bot"
