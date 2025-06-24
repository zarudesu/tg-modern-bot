#!/bin/bash

# HHIVP IT-Outsource System - Быстрое развертывание
# Автоматическое развертывание всех компонентов системы

set -e

echo "🚀 Начинаем развертывание HHIVP IT-System..."

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функция логирования
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка зависимостей
check_dependencies() {
    log_info "Проверяем зависимости..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker не установлен!"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose не установлен!"
        exit 1
    fi
    
    log_success "Все зависимости установлены"
}

# Проверка .env файла
check_env() {
    log_info "Проверяем конфигурацию..."
    
    if [ ! -f .env ]; then
        log_error "Файл .env не найден! Скопируйте .env.example в .env и заполните"
        exit 1
    fi
    
    # Проверяем основные переменные
    source .env
    
    if [ -z "$POSTGRES_PASSWORD" ]; then
        log_error "POSTGRES_PASSWORD не установлен в .env"
        exit 1
    fi
    
    if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
        log_error "TELEGRAM_BOT_TOKEN не установлен в .env"
        exit 1
    fi
    
    log_success "Конфигурация корректная"
}

# Создание директорий
create_directories() {
    log_info "Создаем необходимые директории..."
    
    mkdir -p logs
    mkdir -p backup/postgres
    mkdir -p backup/vaultwarden
    mkdir -p backup/bookstack
    mkdir -p configs/netbox
    
    log_success "Директории созданы"
}

# Запуск базы данных
start_database() {
    log_info "Запускаем базу данных..."
    
    docker-compose -f docker-compose.simple.yml up -d postgres redis
    
    log_info "Ждем инициализации БД (30 секунд)..."
    sleep 30
    
    log_success "База данных запущена"
}

# Запуск основных сервисов
start_services() {
    log_info "Запускаем основные сервисы..."
    
    docker-compose -f docker-compose.simple.yml up -d netbox vaultwarden bookstack
    
    log_info "Ждем инициализации сервисов (60 секунд)..."
    sleep 60
    
    log_success "Основные сервисы запущены"
}

# Запуск прокси и бота
start_proxy_and_bot() {
    log_info "Запускаем Nginx Proxy Manager и Telegram Bot..."
    
    docker-compose -f docker-compose.simple.yml up -d nginx-proxy
    
    # Строим и запускаем бота
    docker-compose -f docker-compose.simple.yml build telegram-bot
    docker-compose -f docker-compose.simple.yml up -d telegram-bot
    
    log_success "Proxy и bot запущены"
}

# Проверка статуса
check_status() {
    log_info "Проверяем статус сервисов..."
    
    docker-compose -f docker-compose.simple.yml ps
    
    echo ""
    log_info "Доступные сервисы:"
    echo "🌐 NetBox: http://localhost:8000 (admin/пароль_из_env)"
    echo "🔐 Vaultwarden: http://localhost:8080"
    echo "📚 BookStack: http://localhost:8081"
    echo "⚙️ Nginx Proxy Manager: http://localhost:81 (admin@example.com/changeme)"
    echo ""
    echo "🤖 Telegram Bot: найдите @hhivp_it_bot в Telegram"
    echo ""
    log_success "Развертывание завершено!"
}

# Основная функция
main() {
    echo "=========================================="
    echo "🏢 HHIVP IT-Outsource Management System"
    echo "=========================================="
    echo ""
    
    check_dependencies
    check_env
    create_directories
    start_database
    start_services
    start_proxy_and_bot
    check_status
    
    echo ""
    log_success "✅ Система успешно развернута!"
    echo ""
    echo "📋 Следующие шаги:"
    echo "1. Настройте SSL сертификаты в Nginx Proxy Manager"
    echo "2. Создайте API токены в NetBox и BookStack"
    echo "3. Обновите .env файл с токенами"
    echo "4. Перезапустите telegram-bot: docker-compose -f docker-compose.simple.yml restart telegram-bot"
    echo ""
}

# Запуск
main "$@"
