# 🤖 Modern Telegram Bot - Production Ready

[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.11+-green.svg)](https://python.org/)
[![Telegram](https://img.shields.io/badge/Telegram-Bot%20API-blue.svg)](https://core.telegram.org/bots/api)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue.svg)](https://postgresql.org/)

**Modern production-ready Telegram bot for team management with full integration capabilities.**

---

## ✨ **Key Features**

### 📊 **Work Journal**
- ✅ Create work entries with detailed tracking
- ✅ Multiple worker selection
- ✅ Smart time parsing: "1 hour 30 minutes" → 90 minutes
- ✅ Filter by date, company, worker
- ✅ Export reports

### 🔗 **Integrations**
- ✅ **n8n** - automatic Google Sheets sync
- ✅ **Telegram Groups** - notifications with mentions
- ✅ **PostgreSQL** - reliable data storage
- ✅ **Redis** - caching and sessions

### 🐳 **Production Ready**
- ✅ **Docker** containerization
- ✅ **Alembic** database migrations
- ✅ **Makefile** deployment commands
- ✅ **Health checks** and monitoring
- ✅ **Graceful shutdown**

---

## 🚀 **Quick Start**

### 1️⃣ **Clone and setup**
```bash
git clone https://github.com/yourusername/tg-modern-bot.git
cd tg-modern-bot
cp .env.example .env
```

### 2️⃣ **Get tokens**
1. **Telegram Bot**: Create in [@BotFather](https://t.me/BotFather)
2. **API Credentials**: Get from [my.telegram.org](https://my.telegram.org)
3. **Admin ID**: Find via [@userinfobot](https://t.me/userinfobot)

### 3️⃣ **Configure .env file**
```env
TELEGRAM_TOKEN=your_token_from_botfather
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
ADMIN_USER_IDS=your_telegram_id
```

### 4️⃣ **Launch**
```bash
# Development mode (database in Docker, bot locally)
make dev

# Full stack in Docker
make full-up

# Production deployment
make prod-deploy
```

---

## 📁 **Project Architecture**

```
tg-modern-bot/
├── 📁 app/                    # Main application code
│   ├── 📁 handlers/          # Telegram handlers
│   ├── 📁 services/          # Business logic
│   ├── 📁 database/          # Models and DB
│   ├── 📁 middleware/        # Middleware
│   └── 📁 integrations/      # External APIs
├── 📁 docs/                  # Complete documentation
├── 📁 alembic/              # Database migrations
├── 🐳 docker-compose.yml    # Docker configuration
├── ⚡ Makefile              # Deployment commands
└── 🔧 .env.example         # Configuration template
```

---

## 🛠️ **Development Commands**

### **Development**
```bash
make dev          # Database in Docker, bot locally
make dev-restart  # Restart development
make dev-stop     # Stop
```

### **Database**
```bash
make db-up        # Start PostgreSQL + Redis
make db-shell     # PostgreSQL console  
make db-admin     # pgAdmin web interface
make db-backup    # Create backup
```

### **Production**
```bash
make prod-deploy  # Full deployment
make prod-up      # Start services
make prod-logs    # View logs
make prod-backup  # Production backup
```

### **Testing**
```bash
make test                    # Run all tests
python test_work_journal.py  # Work journal test
python test_basic.py         # Basic functionality
```

---

## 🔐 **Security**

### ✅ **Secure configuration**
- 🔒 Tokens only in `.env` files (not in Git)
- 🔒 Authorization via `ADMIN_USER_IDS`
- 🔒 Data validation through Pydantic
- 🔒 SQL Injection protection via SQLAlchemy ORM

### ✅ **Production ready**  
- 🔒 Environment variables for all secrets
- 🔒 Docker secrets support
- 🔒 Rate limiting configured
- 🔒 Complete action logging

---

## 📊 **System Modules**

### 🎯 **Work Journal** *(v1.1 - Ready)*
- Create entries through convenient interface
- Multiple worker selection  
- Smart work time parser
- Entry filtering and search
- Export in various formats

### 🔗 **n8n Integration** *(v1.1 - Ready)*
- Automatic Google Sheets sync
- Webhook with retry mechanism
- Structured JSON data
- Complete operation logging

### 📢 **Mention System** *(v1.1 - Ready)*
- Worker mentions in Telegram
- Plane integration for tasks  
- Group notifications
- Flexible notification settings

---

## 📚 **Documentation**

### 📖 **Main documentation**
- [**Quick Start**](docs/QUICK_START.md) - First steps
- [**Development Guide**](DEV_GUIDE.md) - Detailed development guide
- [**Production Deployment**](PRODUCTION_DEPLOYMENT.md) - Production setup
- [**Architecture**](ARCHITECTURE.md) - Technical architecture

### 🔧 **Integrations**
- [**n8n + Google Sheets**](docs/N8N_GOOGLE_SHEETS_INTEGRATION_GUIDE.md)
- [**Google Sheets Integration**](docs/GOOGLE_SHEETS_INTEGRATION_GUIDE.md)

### 🔐 **Security**
- [**Security Notice**](SECURITY_NOTICE.md) - Important information
- [**Security Policy**](SECURITY.md) - Recommendations

---

## 🛡️ **Requirements**

### **Minimum requirements:**
- 🐧 **OS**: Linux/macOS/Windows + Docker
- 🐍 **Python**: 3.11+
- 🐳 **Docker**: 20.10+
- 💾 **RAM**: 512MB+ 
- 💿 **Storage**: 1GB+

### **Production requirements:**
- 🖥️ **VPS**: 1 vCPU, 1GB RAM, 10GB SSD
- 🌐 **Domain**: For webhooks (optional)
- 🔐 **SSL**: Let's Encrypt automatically
- 📊 **Monitoring**: Built-in health checks

---

## 🤝 **Contributing**

### **Contributions welcome!**
1. 🍴 Fork repository
2. 🌟 Create feature branch
3. 🔧 Make changes
4. ✅ Add tests
5. 📝 Update documentation
6. 🚀 Create Pull Request

### **Report issues:**
- 🐛 [Issues](https://github.com/yourusername/tg-modern-bot/issues) - Bugs and suggestions
- 💬 [Discussions](https://github.com/yourusername/tg-modern-bot/discussions) - Questions and ideas

---

## 📜 **License**

This project is distributed under **MIT License**.  
See [LICENSE](LICENSE) file for details.

---

## 🏆 **Project Status**

**✅ Production Ready v2.0** - Ready for production use!

### **🎯 Roadmap v2.1:**
- [ ] REST API for external integrations
- [ ] Web administration interface  
- [ ] Extended role system
- [ ] NetBox integration
- [ ] Slack/Discord support

---

**🚀 Ready to use! Deploy and automate your team!**

---

*📅 Last update: August 2025*  
*⭐ Star if this project is helpful!*
