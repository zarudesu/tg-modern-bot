# Setup Guide for New Computer

## Quick Start

### 1. Clone Repository
```bash
# Navigate to projects directory
cd ~/Projects  # or your preferred location

# Clone from GitHub
git clone git@github.com:zarudesu/tg-modern-bot.git
cd tg-modern-bot

# Or if SSH not configured yet, use HTTPS:
git clone https://github.com/zarudesu/tg-modern-bot.git
cd tg-modern-bot
```

### 2. Copy Environment File
```bash
# Copy secrets from old computer or SECRETS.md
cp .env.example .env

# Edit with your credentials (see SECRETS.md)
vim .env
```

**Required variables:**
- `TELEGRAM_TOKEN` - Bot token
- `DATABASE_URL` - PostgreSQL connection string
- `ADMIN_USER_IDS` - Your Telegram ID
- See `.env.example` for full list

### 3. Install Dependencies

**Option A: Docker (Recommended)**
```bash
# Start everything with Docker
make dev

# Or manually:
docker-compose up -d
```

**Option B: Local Development**
```bash
# Install Python 3.11+
python3 --version

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start database only
make db-up

# Run bot locally
python -m app.main
```

### 4. Setup SSH Keys for Production

```bash
# Generate SSH key (if you don't have one)
ssh-keygen -t rsa -b 4096 -C "your_email@example.com"

# Copy key to production server
ssh-copy-id hhivp@rd.hhivp.com

# Test connection
ssh hhivp@rd.hhivp.com "echo 'SSH works!'"

# Now deploy.sh will work without password
./deploy.sh status
```

### 5. Verify Setup

```bash
# Check bot is running
make bot-logs

# Test in Telegram
# Send /start to @hhivp_it_bot
```

---

## Detailed Setup

### Prerequisites

**Required:**
- Git
- Python 3.11+
- Docker & Docker Compose (for containerized dev)
- PostgreSQL 15+ (for local dev)
- Redis (for local dev)

**Optional:**
- VS Code with Python extension
- Postman (for webhook testing)

### Git Configuration

```bash
# Set your identity (if not done globally)
git config user.name "Your Name"
git config user.email "your.email@example.com"

# Verify configuration
git config --list
```

### SSH Configuration

**For GitHub:**
```bash
# Check if you have SSH key
ls -la ~/.ssh/id_rsa.pub

# If not, generate one
ssh-keygen -t rsa -b 4096 -C "your_email@example.com"

# Add to GitHub
cat ~/.ssh/id_rsa.pub
# Copy output and add to: https://github.com/settings/keys

# Test connection
ssh -T git@github.com
```

**For Production Server:**
```bash
# Copy your SSH key to production
ssh-copy-id hhivp@rd.hhivp.com

# Test connection
ssh hhivp@rd.hhivp.com "echo 'Connected!'"
```

### Environment Variables

Copy from old computer or `SECRETS.md`:

```bash
# Required
TELEGRAM_TOKEN=7946588372:AAE...
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abc123...
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/db
REDIS_URL=redis://localhost:6379/0
ADMIN_USER_IDS=123456789,987654321

# Plane.so
PLANE_API_URL=https://plane.hhivp.com
PLANE_API_TOKEN=plane_xxxx
PLANE_WORKSPACE_SLUG=hhivp

# n8n
N8N_WEBHOOK_URL=https://n8n.hhivp.com/webhook/...
N8N_WEBHOOK_SECRET=secret_here

# Google Sheets
GOOGLE_SHEETS_ID=your_spreadsheet_id

# AI (optional)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

### Database Setup

**Option A: Docker (Recommended)**
```bash
# Start PostgreSQL + Redis
make db-up

# Run migrations
docker exec -it telegram-bot-app alembic upgrade head
```

**Option B: Local PostgreSQL**
```bash
# Install PostgreSQL
brew install postgresql@15  # macOS
# or: sudo apt install postgresql-15  # Ubuntu

# Start PostgreSQL
brew services start postgresql@15

# Create database
createdb hhivp_bot_dev

# Update .env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost/hhivp_bot_dev

# Run migrations
alembic upgrade head
```

### IDE Setup (VS Code)

**Recommended Extensions:**
- Python (ms-python.python)
- Pylance (ms-python.vscode-pylance)
- Docker (ms-azuretools.vscode-docker)
- GitLens (eamodio.gitlens)

**Settings (.vscode/settings.json):**
```json
{
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true,
  "python.formatting.provider": "black",
  "python.linting.mypyEnabled": true,
  "editor.formatOnSave": true,
  "python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python"
}
```

---

## Development Workflow

### Daily Workflow

```bash
# 1. Pull latest changes
git pull

# 2. Start bot
make dev-restart

# 3. Make changes
vim app/...

# 4. Test locally
# Bot auto-reloads on code changes

# 5. Commit changes
git add .
git commit -m "Description"

# 6. Push to GitHub
git push

# 7. Deploy to production
./deploy.sh full
```

### Testing

```bash
# Run tests
make test

# Module isolation (CRITICAL!)
python3 test_modules_isolation.py

# Email filter tests
python3 test_email_fix.py
```

### Code Quality

```bash
# Format code
make format

# Type checking
make typecheck

# Lint
flake8 app/
```

---

## Troubleshooting

### Issue: Python version mismatch
```bash
# Check version
python3 --version  # Should be 3.11+

# Install correct version (macOS)
brew install python@3.11

# Update virtual environment
rm -rf venv
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Issue: Database connection failed
```bash
# Check if PostgreSQL is running
docker ps | grep postgres
# or: brew services list

# Start database
make db-up

# Check DATABASE_URL in .env
echo $DATABASE_URL
```

### Issue: SSH key not working
```bash
# Check SSH agent
ssh-add -l

# Add key if needed
ssh-add ~/.ssh/id_rsa

# Test connection
ssh -v hhivp@rd.hhivp.com
```

### Issue: Docker permission denied (Linux)
```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Log out and log back in, then:
docker ps
```

### Issue: Port already in use
```bash
# Find what's using port 8080
lsof -i :8080

# Kill process
kill -9 <PID>

# Or use different port in docker-compose.yml
```

---

## Checklist for New Computer

- [ ] Clone repository
- [ ] Copy `.env` file with credentials
- [ ] Install Python 3.11+
- [ ] Install Docker & Docker Compose
- [ ] Setup virtual environment
- [ ] Install dependencies (`pip install -r requirements.txt`)
- [ ] Setup SSH key for GitHub
- [ ] Setup SSH key for production server
- [ ] Start database (`make db-up`)
- [ ] Run migrations (`alembic upgrade head`)
- [ ] Start bot (`make dev`)
- [ ] Test bot in Telegram (`/start`)
- [ ] Test deployment (`./deploy.sh status`)
- [ ] Configure IDE (VS Code settings)
- [ ] Run tests (`make test`)

---

## Migration from Old Computer

### Copy These Files (NOT in git):
```bash
# On OLD computer
cd ~/Projects/tg-modern-bot

# Copy these to new computer:
# 1. Environment file
scp .env new-computer:~/Projects/tg-modern-bot/

# 2. SSH keys (if needed)
scp ~/.ssh/id_rsa new-computer:~/.ssh/
scp ~/.ssh/id_rsa.pub new-computer:~/.ssh/
```

### On NEW computer:
```bash
# Set correct permissions for SSH keys
chmod 600 ~/.ssh/id_rsa
chmod 644 ~/.ssh/id_rsa.pub

# Verify .env file
cat .env | grep TELEGRAM_TOKEN
```

---

## Production Access

**After SSH key setup:**
```bash
# Quick status check
./deploy.sh status

# View logs
./deploy.sh logs

# Full deployment
./deploy.sh full
```

---

## Useful Commands

### Development
```bash
make dev                # Start bot in development mode
make dev-restart        # Restart bot (fast)
make dev-stop           # Stop bot
make bot-logs           # View bot logs
```

### Database
```bash
make db-up              # Start PostgreSQL + Redis
make db-down            # Stop database
make db-shell           # PostgreSQL console
make db-backup          # Backup database
```

### Production
```bash
./deploy.sh full        # Full deployment
./deploy.sh quick       # Quick deployment
./deploy.sh logs        # View logs
./deploy.sh status      # Check status
```

### Testing
```bash
make test               # Run tests
make format             # Format code
make typecheck          # Type checking
```

---

## See Also

- [CLAUDE.md](../CLAUDE.md) - Full development guide
- [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment guide
- [README.md](../README.md) - Project overview
- [README_DOCKER.md](../README_DOCKER.md) - Docker guide

---

## Support

**If you get stuck:**
1. Check CLAUDE.md for detailed documentation
2. View logs: `make bot-logs` or `./deploy.sh logs`
3. Check GitHub issues
4. Ask for help in team chat

**Common Resources:**
- GitHub: https://github.com/zarudesu/tg-modern-bot
- Production Bot: @hhivp_it_bot
- n8n: https://n8n.hhivp.com
- Plane: https://plane.hhivp.com
