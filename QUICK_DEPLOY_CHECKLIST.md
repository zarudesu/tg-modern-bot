# 📋 Quick Deploy Checklist

> **Production deployment verification checklist**

---

## ✅ PRE-DEPLOYMENT

### 🔐 **Security:**
- [ ] `.env.prod` configured with production tokens
- [ ] Database passwords changed from defaults
- [ ] Admin user IDs updated
- [ ] No sensitive data in Git history

### 🗄️ **Database:**
- [ ] PostgreSQL running
- [ ] Redis running  
- [ ] Database migrations applied
- [ ] Backup strategy configured

### 🌐 **Network:**
- [ ] Firewall configured (ports 5432, 6379 internal only)
- [ ] Domain/subdomain configured (if using webhooks)
- [ ] SSL certificates ready

---

## 🚀 DEPLOYMENT STEPS

### 1️⃣ **Server preparation:**
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker and Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo pip3 install docker-compose

# Clone repository
git clone <your-repo-url>
cd tg-modern-bot
```

### 2️⃣ **Configuration:**
```bash
# Copy and configure environment
cp .env.example .env.prod

# Edit production settings
nano .env.prod
```

### 3️⃣ **Deploy:**
```bash
# Start production stack
make prod-deploy

# Or manually:
docker-compose -f docker-compose.prod.yml up -d
```

---

## ✅ POST-DEPLOYMENT

### 🔍 **Verification:**
- [ ] Bot responds to `/start` command
- [ ] Database connection working
- [ ] Redis connection working
- [ ] Logs show no errors
- [ ] Work journal functionality working

### 📊 **Monitoring:**
- [ ] Health check endpoint responding
- [ ] Log rotation configured
- [ ] Disk space monitored
- [ ] Memory usage acceptable

### 🧪 **Testing:**
```bash
# Quick tests
python test_basic.py
python test_work_journal.py

# Check services
make status
make prod-logs
```

---

## 🔧 COMMANDS

### **Production management:**
```bash
make prod-deploy   # Full deployment
make prod-up       # Start services
make prod-down     # Stop services
make prod-logs     # View logs
make prod-backup   # Create backup
```

### **Maintenance:**
```bash
make db-backup     # Database backup
make db-shell      # Database console
docker system prune -a  # Clean unused images
```

---

## 🚨 TROUBLESHOOTING

### **Bot not starting:**
```bash
make prod-logs     # Check bot logs
make db-up         # Ensure DB is running
```

### **Database issues:**
```bash
make db-shell      # Connect to database
make db-logs       # Check DB logs
```

### **Memory/disk issues:**
```bash
docker stats       # Resource usage
df -h             # Disk space
free -h           # Memory usage
```

---

## 📞 SUPPORT

- Check logs first: `make prod-logs`
- Database console: `make db-shell`  
- Service status: `make status`
- Create issue if problem persists

---

*📅 Last update: August 2025*
