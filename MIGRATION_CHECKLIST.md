# Migration to New Computer - Quick Checklist

## 🎯 Quick Reference

**What you need from OLD computer:**
1. `.env` file (credentials)
2. `~/.ssh/id_rsa` (SSH private key)
3. `~/.ssh/id_rsa.pub` (SSH public key)
4. (Optional) Local database backup

---

## 📋 Step-by-Step Migration

### On OLD Computer

```bash
# 1. Ensure everything is committed and pushed
cd ~/Projects/tg-modern-bot
git status
git add .
git commit -m "Save work before migration"
git push

# 2. Copy .env file to safe location
cp .env ~/Desktop/bot-env-backup.txt

# 3. Copy SSH keys to safe location (if not already on GitHub)
cp ~/.ssh/id_rsa ~/Desktop/ssh-key-backup
cp ~/.ssh/id_rsa.pub ~/Desktop/ssh-key-backup.pub

# 4. Note your Git config
git config --global user.name
git config --global user.email

# 5. (Optional) Backup local database if needed
make db-backup
```

### On NEW Computer

```bash
# 1. Install prerequisites
# - Git
# - Python 3.11+
# - Docker Desktop (or Docker + Docker Compose)

# 2. Clone repository
cd ~/Projects  # or your preferred location
git clone git@github.com:zarudesu/tg-modern-bot.git
# If SSH not setup yet: git clone https://github.com/zarudesu/tg-modern-bot.git
cd tg-modern-bot

# 3. Copy .env file
# From old computer or transfer file, then:
mv ~/Desktop/bot-env-backup.txt .env
# or create new: cp .env.example .env && vim .env

# 4. Setup SSH keys (if not already configured)
mkdir -p ~/.ssh
mv ~/Desktop/ssh-key-backup ~/.ssh/id_rsa
mv ~/Desktop/ssh-key-backup.pub ~/.ssh/id_rsa.pub
chmod 600 ~/.ssh/id_rsa
chmod 644 ~/.ssh/id_rsa.pub

# 5. Configure Git
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"

# 6. Setup SSH for GitHub (if needed)
cat ~/.ssh/id_rsa.pub
# Add to: https://github.com/settings/keys
ssh -T git@github.com  # Test connection

# 7. Setup SSH for production server
ssh-copy-id hhivp@rd.hhivp.com
ssh hhivp@rd.hhivp.com "echo 'Connected!'"  # Test

# 8. Start development environment
make dev

# 9. Verify bot is working
make bot-logs
# Send /start to @hhivp_it_bot in Telegram

# 10. Test production deployment
./deploy.sh status
```

---

## ⚡ Quick Setup (Minimal)

```bash
# 1. Clone
git clone git@github.com:zarudesu/tg-modern-bot.git
cd tg-modern-bot

# 2. Copy .env from old computer or SECRETS.md
cp .env.example .env
vim .env  # Add credentials

# 3. Start
make dev

# 4. Verify
make bot-logs
```

---

## 📦 What to Transfer

### MUST Transfer (NOT in git):
- [x] `.env` - Environment variables and credentials
- [x] `~/.ssh/id_rsa` - SSH private key (for GitHub & production)
- [x] `~/.ssh/id_rsa.pub` - SSH public key

### Optional:
- [ ] Local database backup (if you have local test data)
- [ ] VS Code settings (`.vscode/` - already in git)
- [ ] Git configuration (username, email)

### DON'T Transfer (already in git):
- ❌ Source code (git clone will get latest)
- ❌ Virtual environment (`venv/`)
- ❌ Docker images (will rebuild)
- ❌ Dependencies (`node_modules/`, `__pycache__/`)
- ❌ Logs (`logs/`)

---

## 🔑 SSH Keys Management

### Option 1: Transfer existing keys (Recommended)
```bash
# Copy from old computer
scp -r old-computer:~/.ssh/id_rsa* ~/.ssh/
chmod 600 ~/.ssh/id_rsa
chmod 644 ~/.ssh/id_rsa.pub
```

### Option 2: Generate new keys
```bash
# Generate new key
ssh-keygen -t rsa -b 4096 -C "your_email@example.com"

# Add to GitHub
cat ~/.ssh/id_rsa.pub
# Copy and add to: https://github.com/settings/keys

# Add to production server
ssh-copy-id hhivp@rd.hhivp.com
```

---

## ✅ Verification Checklist

Run these commands to verify everything works:

```bash
# Git
git status                              # ✅ Should show "On branch main"
git pull                                # ✅ Should update or say "Already up to date"

# SSH - GitHub
ssh -T git@github.com                   # ✅ Should say "Hi zarudesu!"

# SSH - Production
ssh hhivp@rd.hhivp.com "echo OK"       # ✅ Should print "OK"

# Environment
cat .env | grep TELEGRAM_TOKEN          # ✅ Should show your bot token

# Development
make dev                                # ✅ Should start bot
make bot-logs                           # ✅ Should show "Bot started"

# Production
./deploy.sh status                      # ✅ Should show container running
```

---

## 🐛 Common Issues

### Issue: git clone fails with "Permission denied"
```bash
# Solution: Setup SSH key for GitHub first
ssh-keygen -t rsa -b 4096 -C "your_email@example.com"
cat ~/.ssh/id_rsa.pub
# Add to https://github.com/settings/keys

# Or use HTTPS for now:
git clone https://github.com/zarudesu/tg-modern-bot.git
```

### Issue: .env file missing
```bash
# Solution: Copy from old computer or create from SECRETS.md
cp .env.example .env
# Edit with credentials from SECRETS.md or old .env
vim .env
```

### Issue: Python version too old
```bash
# Check version
python3 --version  # Need 3.11+

# macOS: Install correct version
brew install python@3.11

# Ubuntu: Install correct version
sudo apt install python3.11 python3.11-venv
```

### Issue: Docker not installed
```bash
# macOS: Install Docker Desktop
# Download from: https://www.docker.com/products/docker-desktop

# Ubuntu: Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
# Log out and back in
```

### Issue: deploy.sh doesn't work
```bash
# Make executable
chmod +x deploy.sh

# Setup SSH key for production
ssh-copy-id hhivp@rd.hhivp.com

# Test SSH
ssh hhivp@rd.hhivp.com "echo OK"
```

---

## 📚 Full Documentation

For detailed setup instructions, see:
- [docs/NEW_COMPUTER_SETUP.md](docs/NEW_COMPUTER_SETUP.md) - Complete setup guide
- [CLAUDE.md](CLAUDE.md) - Development guide
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) - Deployment guide
- [README.md](README.md) - Project overview

---

## 🎉 You're Done!

After completing this checklist:
- ✅ Bot is running locally
- ✅ Git is configured
- ✅ SSH keys work for GitHub and production
- ✅ Can deploy to production with `./deploy.sh`

**Next steps:**
1. Make a test change and commit: `git add . && git commit -m "Test"`
2. Deploy to production: `./deploy.sh status`
3. Start coding! 🚀

**Need help?** Check [docs/NEW_COMPUTER_SETUP.md](docs/NEW_COMPUTER_SETUP.md) for troubleshooting.
