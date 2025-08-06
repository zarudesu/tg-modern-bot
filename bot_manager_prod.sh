#!/bin/bash

# HHIVP IT Assistant Bot Manager - Production Version
# Скрипт для управления ботом в продакшене

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Конфигурация для продакшена
PROJECT_DIR="/opt/hhivp-it-bot"  # Стандартная директория для продакшена
BOT_NAME="HHIVP IT Assistant Bot"
PYTHON_VENV="$PROJECT_DIR/venv/bin/python"
BOT_MODULE="app.main"
PID_FILE="$PROJECT_DIR/bot.pid"
LOG_FILE="$PROJECT_DIR/logs/bot_production.log"
SERVICE_USER="hhivp-bot"  # Пользователь для запуска сервиса

# Функции логирования (те же что и в dev версии)
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$PROJECT_DIR/logs/manager.log"
}

log_success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} ✅ $1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] SUCCESS: $1" >> "$PROJECT_DIR/logs/manager.log"
}

log_warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} ⚠️  $1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1" >> "$PROJECT_DIR/logs/manager.log"
}

log_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} ❌ $1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" >> "$PROJECT_DIR/logs/manager.log"
}

# Функция поиска процессов бота
find_bot_processes() {
    local pids=$(ps aux | grep -E "python.*app\.main|python.*-m app\.main" | grep -v grep | awk '{print $2}')
    echo "$pids"
}

# Функция остановки всех процессов
stop_all_bots() {
    log "Остановка всех копий бота..."
    
    local pids=$(find_bot_processes)
    
    if [ -z "$pids" ]; then
        log_warning "Запущенные копии бота не найдены"
        # Удаляем PID файл если он есть
        [ -f "$PID_FILE" ] && rm -f "$PID_FILE"
        return 0
    fi
    
    local count=0
    for pid in $pids; do
        if kill -0 "$pid" 2>/dev/null; then
            log "Остановка процесса PID: $pid"
            
            # Graceful shutdown
            if kill -TERM "$pid" 2>/dev/null; then
                for i in {1..10}; do  # Больше времени для продакшена
                    if ! kill -0 "$pid" 2>/dev/null; then
                        log_success "Процесс $pid остановлен (graceful)"
                        count=$((count + 1))
                        break
                    fi
                    sleep 1
                done
                
                # Принудительная остановка если нужно
                if kill -0 "$pid" 2>/dev/null; then
                    log_warning "Принудительная остановка процесса $pid"
                    kill -KILL "$pid" 2>/dev/null || true
                    sleep 2
                    if ! kill -0 "$pid" 2>/dev/null; then
                        log_success "Процесс $pid принудительно остановлен"
                        count=$((count + 1))
                    fi
                fi
            fi
        fi
    done
    
    # Удаляем PID файл
    [ -f "$PID_FILE" ] && rm -f "$PID_FILE"
    
    if [ $count -gt 0 ]; then
        log_success "Остановлено процессов: $count"
    fi
}

# Проверка окружения для продакшена
check_environment() {
    log "Проверка окружения (Production)..."
    
    # Проверяем права доступа
    if [ "$EUID" -eq 0 ]; then
        log_warning "Скрипт запущен от root. Рекомендуется использовать отдельного пользователя."
    fi
    
    # Проверяем директорию проекта
    if [ ! -d "$PROJECT_DIR" ]; then
        log_error "Директория проекта не найдена: $PROJECT_DIR"
        exit 1
    fi
    
    cd "$PROJECT_DIR" || exit 1
    
    # Проверяем критические файлы
    local required_files=("$PYTHON_VENV" ".env" "app/main.py")
    for file in "${required_files[@]}"; do
        if [ ! -f "$file" ]; then
            log_error "Необходимый файл не найден: $file"
            exit 1
        fi
    done
    
    # Создаем директории
    mkdir -p logs
    mkdir -p backups
    
    # Проверяем права на запись
    if [ ! -w "logs" ]; then
        log_error "Нет прав на запись в директорию logs"
        exit 1
    fi
    
    log_success "Окружение проверено"
}

# Функция запуска бота в продакшене
start_bot() {
    log "Запуск $BOT_NAME (Production)..."
    
    # Проверяем, что нет запущенных процессов
    local running=$(find_bot_processes)
    if [ ! -z "$running" ]; then
        log_error "Найдены запущенные процессы: $running"
        exit 1
    fi
    
    # Создаем бэкап текущих логов
    if [ -f "$LOG_FILE" ]; then
        mv "$LOG_FILE" "$LOG_FILE.$(date +%Y%m%d_%H%M%S)"
    fi
    
    # Запускаем бота
    log "Запуск: $PYTHON_VENV -m $BOT_MODULE"
    
    # Production запуск с полным логированием
    nohup "$PYTHON_VENV" -m "$BOT_MODULE" > "$LOG_FILE" 2>&1 &
    local bot_pid=$!
    
    # Сохраняем PID
    echo "$bot_pid" > "$PID_FILE"
    
    log "Бот запущен с PID: $bot_pid"
    
    # Проверяем запуск
    sleep 5
    
    if kill -0 "$bot_pid" 2>/dev/null; then
        log_success "$BOT_NAME успешно запущен (PID: $bot_pid)"
        log "Логи: tail -f $LOG_FILE"
        
        # Отправляем уведомление о запуске (если настроено)
        send_notification "✅ $BOT_NAME запущен успешно (PID: $bot_pid)"
        
        return 0
    else
        log_error "Не удалось запустить бота"
        log "Проверьте логи: cat $LOG_FILE"
        rm -f "$PID_FILE"
        exit 1
    fi
}

# Функция отправки уведомлений (опционально)
send_notification() {
    local message="$1"
    # Здесь можно добавить отправку в Slack, Discord, email и т.д.
    # Например:
    # curl -X POST -H 'Content-type: application/json' \
    #      --data "{\"text\":\"$message\"}" \
    #      "$SLACK_WEBHOOK_URL" 2>/dev/null || true
}

# Функция показа статуса для продакшена
show_status() {
    log "Статус бота (Production)..."
    
    local pids=$(find_bot_processes)
    
    if [ -z "$pids" ]; then
        echo -e "${RED}❌ Бот не запущен${NC}"
        
        # Проверяем PID файл
        if [ -f "$PID_FILE" ]; then
            log_warning "Найден устаревший PID файл, удаляем"
            rm -f "$PID_FILE"
        fi
        
        return 1
    else
        echo -e "${GREEN}✅ Бот запущен${NC}"
        echo
        
        # Показываем информацию о процессах
        echo "Процессы:"
        ps aux | grep -E "python.*app\.main" | grep -v grep | while read line; do
            echo "  $line"
        done
        
        # Показываем uptime
        if [ -f "$PID_FILE" ]; then
            local pid=$(cat "$PID_FILE")
            if kill -0 "$pid" 2>/dev/null; then
                local start_time=$(ps -o lstart= -p "$pid" 2>/dev/null || echo "Unknown")
                echo "  Время запуска: $start_time"
                
                # Показываем использование ресурсов
                local cpu_mem=$(ps -o %cpu,%mem -p "$pid" --no-headers 2>/dev/null || echo "N/A N/A")
                echo "  CPU/Memory: $cpu_mem"
            fi
        fi
        
        # Показываем последние логи
        echo
        echo "Логи (последние 15 строк):"
        if [ -f "$LOG_FILE" ]; then
            tail -15 "$LOG_FILE" | sed 's/^/  /'
        else
            echo "  Файл логов не найден"
        fi
        
        return 0
    fi
}

# Функция для мониторинга (используется для health checks)
health_check() {
    local pids=$(find_bot_processes)
    
    if [ -z "$pids" ]; then
        echo "UNHEALTHY: No bot processes running"
        exit 1
    fi
    
    # Проверяем, что процесс отвечает (можно добавить HTTP health check)
    # Пока просто проверяем, что процесс жив
    for pid in $pids; do
        if ! kill -0 "$pid" 2>/dev/null; then
            echo "UNHEALTHY: Process $pid not responding"
            exit 1
        fi
    done
    
    echo "HEALTHY: Bot is running"
    exit 0
}

# Функция очистки логов
cleanup_logs() {
    log "Очистка старых логов..."
    
    # Удаляем логи старше 30 дней
    find "$PROJECT_DIR/logs" -name "*.log*" -mtime +30 -delete 2>/dev/null || true
    
    # Ротируем текущий лог если он больше 100MB
    if [ -f "$LOG_FILE" ] && [ $(stat -f%z "$LOG_FILE" 2>/dev/null || echo 0) -gt 104857600 ]; then
        mv "$LOG_FILE" "$LOG_FILE.$(date +%Y%m%d_%H%M%S)"
        log_success "Лог файл ротирован"
    fi
}

# Создание необходимых директорий
mkdir -p "$PROJECT_DIR/logs"

# Основная логика
case "${1:-}" in
    "start")
        check_environment
        stop_all_bots
        start_bot
        ;;
    "stop")
        stop_all_bots
        ;;
    "restart")
        check_environment
        stop_all_bots
        sleep 3
        start_bot
        ;;
    "status")
        show_status
        ;;
    "health")
        health_check
        ;;
    "cleanup")
        cleanup_logs
        ;;
    "help"|"-h"|"--help")
        echo "Production Bot Manager - Использование: $0 {start|stop|restart|status|health|cleanup|help}"
        echo ""
        echo "Команды:"
        echo "  start    - Запустить бота"
        echo "  stop     - Остановить бота"
        echo "  restart  - Перезапустить бота"
        echo "  status   - Показать статус и логи"
        echo "  health   - Health check (для мониторинга)"
        echo "  cleanup  - Очистить старые логи"
        echo "  help     - Показать справку"
        ;;
    "")
        log_warning "Команда не указана. Используйте 'help' для справки"
        show_status
        ;;
    *)
        log_error "Неизвестная команда: $1"
        exit 1
        ;;
esac
