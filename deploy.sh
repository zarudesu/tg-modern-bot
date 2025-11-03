#!/bin/bash

# ============================================================================
# Production Deployment Script for tg-modern-bot
# ============================================================================
#
# Usage:
#   ./deploy.sh [command] [options]
#
# Commands:
#   push              - Push code to GitHub
#   pull              - Pull latest code on server
#   build             - Rebuild Docker image (--no-cache)
#   rebuild           - Rebuild and restart bot container
#   restart           - Restart bot container only
#   logs              - View bot logs (real-time)
#   status            - Check bot container status
#   full              - Full deployment (push + pull + rebuild)
#   quick             - Quick deployment (no rebuild, just restart)
#
# Options:
#   --no-cache        - Force clean Docker build (slow but safe)
#   --tail N          - Show last N log lines (default: 50)
#
# Examples:
#   ./deploy.sh full              # Complete deployment
#   ./deploy.sh rebuild           # Rebuild after code changes
#   ./deploy.sh restart           # Quick restart (no code changes)
#   ./deploy.sh logs --tail 100   # Show last 100 lines
#
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SSH_HOST="hhivp@rd.hhivp.com"
PROJECT_PATH="/opt/tg-modern-bot"
COMPOSE_FILE="docker-compose.prod.yml"
BOT_CONTAINER="hhivp-bot-app-prod"
LOG_TAIL=50

# SSH connection string (using ~/.ssh/id_rsa by default)
SSH_CMD="ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 ${SSH_HOST}"

# Helper functions
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

# Parse options
NO_CACHE=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --no-cache)
            NO_CACHE="--no-cache"
            shift
            ;;
        --tail)
            LOG_TAIL="$2"
            shift 2
            ;;
        *)
            COMMAND="$1"
            shift
            ;;
    esac
done

# Commands

cmd_push() {
    log_info "Pushing code to GitHub..."
    git push
    log_success "Code pushed to GitHub"
}

cmd_pull() {
    log_info "Pulling latest code on production server..."
    $SSH_CMD "cd ${PROJECT_PATH} && git pull"
    log_success "Code pulled on server"
}

cmd_build() {
    log_info "Building Docker image ${NO_CACHE}..."
    if [ -n "$NO_CACHE" ]; then
        log_warning "Using --no-cache: build will be slow but clean"
    fi
    $SSH_CMD "cd ${PROJECT_PATH} && docker-compose -f ${COMPOSE_FILE} build ${NO_CACHE} bot"
    log_success "Docker image built"
}

cmd_rebuild() {
    log_info "Rebuilding bot container..."

    # Stop and remove old container
    log_info "Stopping old container..."
    $SSH_CMD "docker stop ${BOT_CONTAINER} && docker rm ${BOT_CONTAINER}" || true

    # Start new container
    log_info "Starting new container..."
    $SSH_CMD "cd ${PROJECT_PATH} && docker-compose -f ${COMPOSE_FILE} up -d bot"

    log_success "Bot container rebuilt and started"

    # Wait for startup
    sleep 3
    cmd_status
}

cmd_restart() {
    log_info "Restarting bot container..."
    $SSH_CMD "docker restart ${BOT_CONTAINER}"
    log_success "Bot container restarted"

    sleep 3
    cmd_status
}

cmd_logs() {
    log_info "Fetching logs (last ${LOG_TAIL} lines)..."
    $SSH_CMD "docker logs ${BOT_CONTAINER} --tail ${LOG_TAIL} 2>&1 | grep -E 'Started|ERROR|Bot started|✅|INFO'"
}

cmd_status() {
    log_info "Checking bot status..."
    $SSH_CMD "docker ps --filter name=${BOT_CONTAINER} --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
}

cmd_full() {
    log_info "Starting FULL deployment..."
    echo ""

    # 1. Push to GitHub
    cmd_push
    echo ""

    # 2. Pull on server
    cmd_pull
    echo ""

    # 3. Build Docker image
    cmd_build
    echo ""

    # 4. Rebuild container
    cmd_rebuild
    echo ""

    # 5. Show logs
    cmd_logs

    log_success "FULL DEPLOYMENT COMPLETED! 🚀"
}

cmd_quick() {
    log_info "Starting QUICK deployment (no rebuild)..."
    echo ""

    cmd_push
    echo ""
    cmd_pull
    echo ""
    cmd_restart
    echo ""
    cmd_logs

    log_success "QUICK DEPLOYMENT COMPLETED! ⚡"
}

cmd_help() {
    cat << 'EOF'
Production Deployment Script for tg-modern-bot

USAGE:
    ./deploy.sh [command] [options]

COMMANDS:
    push              Push code to GitHub
    pull              Pull latest code on server
    build             Rebuild Docker image
    rebuild           Rebuild and restart bot container
    restart           Restart bot container (no code changes)
    logs              View bot logs
    status            Check bot container status
    full              Full deployment (push + pull + build + rebuild)
    quick             Quick deployment (push + pull + restart)
    help              Show this help message

OPTIONS:
    --no-cache        Force clean Docker build (recommended after dependency changes)
    --tail N          Show last N log lines (default: 50)

EXAMPLES:
    # After code changes - FULL deployment
    ./deploy.sh full --no-cache

    # After minor changes - QUICK deployment
    ./deploy.sh quick

    # Just rebuild container after code changes
    ./deploy.sh rebuild

    # Just restart (for .env changes only)
    ./deploy.sh restart

    # View recent logs
    ./deploy.sh logs --tail 100

    # Check bot status
    ./deploy.sh status

WORKFLOW:
    1. Make code changes locally
    2. Commit changes: git add . && git commit -m "message"
    3. Deploy:
       - Full deploy: ./deploy.sh full
       - Quick deploy: ./deploy.sh quick
    4. Check logs: ./deploy.sh logs

SSH CONNECTION:
    Host: ${SSH_HOST}
    Uses: ~/.ssh/id_rsa (default SSH key)

    If you haven't set up SSH keys yet:
        1. Generate key: ssh-keygen -t rsa -b 4096 -C "your_email@example.com"
        2. Copy to server: ssh-copy-id ${SSH_HOST}
        3. Test: ssh ${SSH_HOST} "echo 'SSH works!'"

EOF
}

# Main command router
case $COMMAND in
    push)
        cmd_push
        ;;
    pull)
        cmd_pull
        ;;
    build)
        cmd_build
        ;;
    rebuild)
        cmd_rebuild
        ;;
    restart)
        cmd_restart
        ;;
    logs)
        cmd_logs
        ;;
    status)
        cmd_status
        ;;
    full)
        cmd_full
        ;;
    quick)
        cmd_quick
        ;;
    help|--help|-h|"")
        cmd_help
        ;;
    *)
        log_error "Unknown command: $COMMAND"
        echo ""
        cmd_help
        exit 1
        ;;
esac
