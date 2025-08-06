# 🚀 Quick Start Guide

## ⚡ Prerequisites

- Docker and Docker Compose installed
- Telegram Bot Token (from @BotFather)
- Basic familiarity with command line

---

## 📦 Installation

### 1. Clone and setup
```bash
git clone https://github.com/yourusername/tg-modern-bot.git
cd tg-modern-bot
cp .env.example .env
```

### 2. Configure environment
```bash
# Edit .env file
nano .env

# Add your tokens:
TELEGRAM_TOKEN=your_bot_token_from_botfather
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
ADMIN_USER_IDS=your_telegram_user_id
```

### 3. Start the bot
```bash
# Development mode (recommended for first run)
make dev

# Or full production stack
make full-up
```

---

## 🧪 Testing

```bash
# Basic functionality test
python test_basic.py

# Work journal test  
python test_work_journal.py

# Check bot status
make status
```

---

## 📱 Using the Bot

1. Start chat with your bot in Telegram
2. Send `/start` to see available commands
3. Use `/work` to access work journal
4. Use `/help` for command list

---

## 🛠️ Development

```bash
# Watch logs
make bot-logs

# Restart after changes
make dev-restart

# Access database console
make db-shell
```

---

## 🔧 Common Commands

```bash
make dev          # Development mode
make dev-restart  # Quick restart
make dev-stop     # Stop development
make db-up        # Database only
make status       # Check services
make clean        # Clean containers
```

---

## 📚 Next Steps

- Read [Technical Spec](TECHNICAL_SPEC.md) for architecture details
- Check [Google Sheets Integration](GOOGLE_SHEETS_INTEGRATION_GUIDE.md) for automation
- See [n8n Integration](N8N_GOOGLE_SHEETS_INTEGRATION_GUIDE.md) for workflows

---

*📅 Last update: August 2025*
