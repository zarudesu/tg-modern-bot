#!/bin/bash

# HHIVP IT-System - Резервное копирование
# Автоматическое создание backup всех данных

set -e

# Настройки
BACKUP_DIR="/opt/hhivp-it-system/backup"
DATE=$(date +%Y%m%d_%H%M%S)
COMPOSE_FILE="docker-compose.simple.yml"

# Цвета
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${YELLOW}[BACKUP]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Создание директорий backup
create_backup_dirs() {
    log_info "Создаем директории для backup..."
    
    mkdir -p $BACKUP_DIR/postgres
    mkdir -p $BACKUP_DIR/vaultwarden
    mkdir -p $BACKUP_DIR/bookstack
    mkdir -p $BACKUP_DIR/netbox
    mkdir -p $BACKUP_DIR/configs
    
    log_success "Директории созданы"
}

# Backup PostgreSQL
backup_postgres() {
    log_info "Создаем backup PostgreSQL..."
    
    # Загружаем переменные из .env
    source .env
    
    # Backup всех баз данных
    docker exec ito-postgres pg_dumpall -U $POSTGRES_USER > $BACKUP_DIR/postgres/full_backup_$DATE.sql
    
    # Отдельные backup для каждой БД
    docker exec ito-postgres pg_dump -U $POSTGRES_USER netbox > $BACKUP_DIR/postgres/netbox_$DATE.sql
    docker exec ito-postgres pg_dump -U $POSTGRES_USER bookstack > $BACKUP_DIR/postgres/bookstack_$DATE.sql
    docker exec ito-postgres pg_dump -U $POSTGRES_USER telegram_bot > $BACKUP_DIR/postgres/telegram_bot_$DATE.sql
    
    log_success "PostgreSQL backup завершен"
}

# Backup Vaultwarden
backup_vaultwarden() {
    log_info "Создаем backup Vaultwarden..."
    
    # Копируем данные Vaultwarden
    docker cp ito-vaultwarden:/data $BACKUP_DIR/vaultwarden/data_$DATE
    
    # Архивируем
    tar -czf $BACKUP_DIR/vaultwarden/vaultwarden_$DATE.tar.gz -C $BACKUP_DIR/vaultwarden data_$DATE
    rm -rf $BACKUP_DIR/vaultwarden/data_$DATE
    
    log_success "Vaultwarden backup завершен"
}

# Backup BookStack
backup_bookstack() {
    log_info "Создаем backup BookStack..."
    
    # Копируем конфигурацию BookStack
    docker cp ito-bookstack:/config $BACKUP_DIR/bookstack/config_$DATE
    
    # Архивируем
    tar -czf $BACKUP_DIR/bookstack/bookstack_$DATE.tar.gz -C $BACKUP_DIR/bookstack config_$DATE
    rm -rf $BACKUP_DIR/bookstack/config_$DATE
    
    log_success "BookStack backup завершен"
}

# Backup NetBox медиа
backup_netbox() {
    log_info "Создаем backup NetBox медиа..."
    
    # Копируем медиа файлы NetBox
    docker cp ito-netbox:/opt/netbox/netbox/media $BACKUP_DIR/netbox/media_$DATE
    
    # Архивируем
    tar -czf $BACKUP_DIR/netbox/netbox_media_$DATE.tar.gz -C $BACKUP_DIR/netbox media_$DATE
    rm -rf $BACKUP_DIR/netbox/media_$DATE
    
    log_success "NetBox backup завершен"
}

# Backup конфигураций
backup_configs() {
    log_info "Создаем backup конфигураций..."
    
    # Копируем все важные конфигурации
    cp -r configs $BACKUP_DIR/configs/configs_$DATE
    cp .env $BACKUP_DIR/configs/env_$DATE
    cp docker-compose*.yml $BACKUP_DIR/configs/
    
    # Архивируем
    tar -czf $BACKUP_DIR/configs/configs_$DATE.tar.gz -C $BACKUP_DIR/configs configs_$DATE
    rm -rf $BACKUP_DIR/configs/configs_$DATE
    
    log_success "Конфигурации backup завершен"
}

# Очистка старых backup
cleanup_old_backups() {
    log_info "Очищаем старые backup (старше 30 дней)..."
    
    find $BACKUP_DIR -type f -name "*.sql" -mtime +30 -delete
    find $BACKUP_DIR -type f -name "*.tar.gz" -mtime +30 -delete
    
    log_success "Очистка завершена"
}

# Главная функция
main() {
    echo "==========================================="
    echo "🔄 HHIVP IT-System Backup"
    echo "==========================================="
    echo ""
    
    log_info "Начинаем создание backup..."
    
    create_backup_dirs
    backup_postgres
    backup_vaultwarden
    backup_bookstack
    backup_netbox
    backup_configs
    cleanup_old_backups
    
    echo ""
    log_success "✅ Backup успешно создан!"
    log_info "📁 Backup сохранен в: $BACKUP_DIR"
    log_info "📅 Дата: $DATE"
    echo ""
}

# Запуск
main "$@"
