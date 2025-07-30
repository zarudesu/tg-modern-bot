#!/bin/bash

# 🚀 Скрипт настройки независимой разработки Telegram бота

echo "🤖 Настройка независимой разработки Telegram бота"
echo "==============================================="

# Проверяем базовые утилиты
if ! command -v bc &> /dev/null; then
    echo "📦 Устанавливаем утилиту bc для сравнения версий..."
    if command -v brew &> /dev/null; then
        brew install bc
    elif command -v apt-get &> /dev/null; then
        sudo apt-get install -y bc
    else
        echo "⚠️  bc не найден, но продолжаем..."
        # Создаем простую функцию для сравнения версий
        version_compare() {
            if [[ $1 == *"3.13"* ]] || [[ $1 == *"3.14"* ]] || [[ $1 == *"3.15"* ]]; then
                return 1  # версия слишком новая
            else
                return 0  # версия подходящая
            fi
        }
    fi
fi

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

# Проверяем Python и находим совместимую версию
echo "🐍 Проверяем Python..."

# Список предпочтительных версий Python (от новой к старой, но совместимых)
PYTHON_VERSIONS=("python3.12" "python3.11" "python3.10" "python3.9" "python3.8" "python3")

PYTHON_CMD=""
for version in "${PYTHON_VERSIONS[@]}"; do
    if command -v $version &> /dev/null; then
        # Проверяем, что версия не 3.13+
        VERSION_NUM=$($version -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        MAJOR=$(echo $VERSION_NUM | cut -d. -f1)
        MINOR=$(echo $VERSION_NUM | cut -d. -f2)
        
        if [ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 13 ]; then
            PYTHON_CMD=$version
            PYTHON_VERSION=$($version --version)
            echo "✅ Совместимый Python найден: $PYTHON_VERSION ($version)"
            break
        else
            echo "⚠️  $version (версия $VERSION_NUM) слишком новая, ищем более старую..."
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "❌ Совместимая версия Python не найдена!"
    echo "   Установите Python 3.8-3.12. Python 3.13+ пока не поддерживается."
    echo "   Попробуйте: brew install python@3.12"
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
    echo "📦 Создаем виртуальное окружение с $PYTHON_CMD..."
    $PYTHON_CMD -m venv venv
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
