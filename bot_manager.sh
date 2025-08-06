#!/bin/bash

# HHIVP IT Assistant Bot Manager
# Скрипт для управления ботом: остановка всех копий и запуск новой

set -e  # Останавливать выполнение при любой ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Директория проекта
PROJECT_DIR="/path/to/your/project"
BOT_NAME="HHIVP IT Assistant Bot"
PYTHON_VENV="$PROJECT_DIR/venv/bin/python"
BOT_MODULE="app.main"

# Функция логирования
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} ✅ $1"
}

log_warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} ⚠️  $1"
}

log_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} ❌ $1"
}

# Функция для поиска процессов бота
find_bot_processes() {
    log "Поиск запущенных процессов бота..."
    
    # Ищем процессы Python с app.main (более точный паттерн)
    local pids=$(ps aux | grep -E "python.*-m app\.main|python.*app\.main" | grep -v grep | grep -v "$0" | awk '{print $2}')
    
    if [ ! -z "$pids" ]; then
        echo "$pids"
    else
        echo ""
    fi
}

# Функция для остановки всех процессов бота
stop_all_bots() {
    log "Остановка всех копий бота..."
    
    local pids=$(find_bot_processes)
    
    if [ -z "$pids" ]; then
        log_warning "Запущенные копии бота не найдены"
        return 0
    fi
    
    local count=0
    for pid in $pids; do
        if kill -0 "$pid" 2>/dev/null; then
            log "Остановка процесса PID: $pid"
            
            # Сначала пробуем мягкую остановку
            if kill -TERM "$pid" 2>/dev/null; then
                # Ждем до 5 секунд для graceful shutdown
                for i in {1..5}; do
                    if ! kill -0 "$pid" 2>/dev/null; then
                        log_success "Процесс $pid остановлен (graceful)"
                        count=$((count + 1))
                        break
                    fi
                    sleep 1
                done
                
                # Если процесс еще жив, убиваем принудительно
                if kill -0 "$pid" 2>/dev/null; then
                    log_warning "Принудительная остановка процесса $pid"
                    kill -KILL "$pid" 2>/dev/null || true
                    sleep 1
                    if ! kill -0 "$pid" 2>/dev/null; then
                        log_success "Процесс $pid принудительно остановлен"
                        count=$((count + 1))
                    fi
                fi
            else
                log_warning "Не удалось остановить процесс $pid"
            fi
        fi
    done
    
    if [ $count -gt 0 ]; then
        log_success "Остановлено процессов: $count"
    else
        log_warning "Ни один процесс не был остановлен"
    fi
    
    # Дополнительная проверка
    sleep 2
    local remaining_pids=$(ps aux | grep -E "python.*-m app\.main|python.*app\.main" | grep -v grep | grep -v "$0" | awk '{print $2}')
    if [ ! -z "$remaining_pids" ]; then
        log_error "Остались запущенные процессы: $remaining_pids"
        return 1
    fi
}

# Функция проверки окружения
check_environment() {
    log "Проверка окружения..."
    
    # Проверяем директорию проекта
    if [ ! -d "$PROJECT_DIR" ]; then
        log_error "Директория проекта не найдена: $PROJECT_DIR"
        exit 1
    fi
    
    # Переходим в директорию проекта
    cd "$PROJECT_DIR" || exit 1
    log "Рабочая директория: $(pwd)"
    
    # Проверяем виртуальное окружение
    if [ ! -f "$PYTHON_VENV" ]; then
        log_error "Python venv не найден: $PYTHON_VENV"
        exit 1
    fi
    
    # Проверяем .env файл
    if [ ! -f ".env" ]; then
        log_error "Файл .env не найден в $PROJECT_DIR"
        exit 1
    fi
    
    # Проверяем модуль бота
    if [ ! -f "app/main.py" ]; then
        log_error "Модуль бота не найден: app/main.py"
        exit 1
    fi
    
    log_success "Окружение проверено"
}

# Функция запуска бота
start_bot() {
    log "Запуск $BOT_NAME..."
    
    # Проверяем, что все процессы остановлены
    local running_pids=$(ps aux | grep -E "python.*-m app\.main|python.*app\.main" | grep -v grep | grep -v "$0" | awk '{print $2}')
    if [ ! -z "$running_pids" ]; then
        log_error "Найдены запущенные процессы бота: $running_pids"
        log_error "Сначала остановите все копии"
        exit 1
    fi
    
    # Запускаем бота
    log "Выполнение: $PYTHON_VENV -m $BOT_MODULE"
    
    # Запуск в фоне с перенаправлением вывода
    nohup "$PYTHON_VENV" -m "$BOT_MODULE" > logs/bot_manager.log 2>&1 &
    local bot_pid=$!
    
    log "Бот запущен с PID: $bot_pid"
    
    # Ждем немного и проверяем, что процесс запустился
    sleep 3
    
    if kill -0 "$bot_pid" 2>/dev/null; then
        log_success "$BOT_NAME успешно запущен (PID: $bot_pid)"
        log "Логи: tail -f $PROJECT_DIR/logs/bot_manager.log"
        return 0
    else
        log_error "Не удалось запустить бота"
        log "Проверьте логи: cat $PROJECT_DIR/logs/bot_manager.log"
        exit 1
    fi
}

# Функция получения статуса
show_status() {
    log "Статус бота..."
    
    local pids=$(find_bot_processes)
    
    if [ -z "$pids" ]; then
        echo -e "${RED}❌ Бот не запущен${NC}"
        return 1
    else
        echo -e "${GREEN}✅ Бот запущен${NC}"
        echo
        echo "Запущенные процессы:"
        ps aux | grep -E "python.*app\.main|python.*-m app\.main" | grep -v grep | while read line; do
            echo "  $line"
        done
        echo
        echo "Логи (последние 10 строк):"
        if [ -f "$PROJECT_DIR/logs/bot_manager.log" ]; then
            tail -10 "$PROJECT_DIR/logs/bot_manager.log" | sed 's/^/  /'
        else
            echo "  Файл логов не найден"
        fi
        return 0
    fi
}

# Функция перезапуска
restart_bot() {
    log "Перезапуск $BOT_NAME..."
    
    stop_all_bots
    sleep 2
    check_environment
    start_bot
}

# Функция показа помощи
show_help() {
    echo "Использование: $0 {start|stop|restart|status|help}"
    echo ""
    echo "Команды:"
    echo "  start    - Запустить бота (после остановки всех копий)"
    echo "  stop     - Остановить все копии бота"
    echo "  restart  - Перезапустить бота"
    echo "  status   - Показать статус бота"
    echo "  help     - Показать эту справку"
    echo ""
    echo "Примеры:"
    echo "  $0 restart  # Перезапустить бота"
    echo "  $0 status   # Проверить статус"
    echo "  $0 stop     # Остановить всех ботов"
}

# Создание директории для логов
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
        restart_bot
        ;;
    "status")
        show_status
        ;;
    "help"|"-h"|"--help")
        show_help
        ;;
    "")
        log_warning "Команда не указана. Выполняется restart..."
        restart_bot
        ;;
    *)
        log_error "Неизвестная команда: $1"
        show_help
        exit 1
        ;;
esac
