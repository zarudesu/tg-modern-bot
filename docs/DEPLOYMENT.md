# Production Deployment Guide

## Quick Reference

### Full Deployment (after code changes)
```bash
./deploy.sh full
```

### Quick Deployment (minor changes, no rebuild)
```bash
./deploy.sh quick
```

### View Logs
```bash
./deploy.sh logs
./deploy.sh logs --tail 100  # Last 100 lines
```

### Check Status
```bash
./deploy.sh status
```

---

## Deploy Script Commands

| Command | Description | When to Use |
|---------|-------------|-------------|
| `./deploy.sh full` | Complete deployment | After code changes, new features |
| `./deploy.sh full --no-cache` | Clean rebuild | After dependency changes (requirements.txt) |
| `./deploy.sh quick` | Fast deployment | Minor fixes, no Docker rebuild needed |
| `./deploy.sh rebuild` | Rebuild container only | After code changes (no git push needed) |
| `./deploy.sh restart` | Restart container | After .env changes only |
| `./deploy.sh logs` | View bot logs | Check bot status, debug issues |
| `./deploy.sh status` | Container status | Quick health check |
| `./deploy.sh push` | Push to GitHub | Manual git push |
| `./deploy.sh pull` | Pull on server | Manual git pull |
| `./deploy.sh build` | Build Docker image | Manual Docker build |

---

## Deployment Workflow

### Standard Workflow
```bash
# 1. Make code changes locally
vim app/modules/...

# 2. Commit changes
git add .
git commit -m "Add new feature"

# 3. Deploy to production
./deploy.sh full

# 4. Verify bot is running
./deploy.sh logs
```

### Fast Workflow (for minor fixes)
```bash
# 1. Make minor fix
vim app/...

# 2. Commit
git add . && git commit -m "Fix typo"

# 3. Quick deploy (no rebuild)
./deploy.sh quick
```

### After Dependency Changes
```bash
# 1. Update requirements.txt
vim requirements.txt

# 2. Commit
git add requirements.txt
git commit -m "Add new dependency"

# 3. Deploy with clean build
./deploy.sh full --no-cache
```

---

## SSH Setup

The deploy script uses SSH keys for passwordless authentication.

### Check if SSH is configured
```bash
ssh hhivp@rd.hhivp.com "echo 'SSH works!'"
```

### Setup SSH keys (if needed)
```bash
# 1. Generate SSH key (if you don't have one)
ssh-keygen -t rsa -b 4096 -C "your_email@example.com"

# 2. Copy key to server
ssh-copy-id hhivp@rd.hhivp.com

# 3. Test connection
ssh hhivp@rd.hhivp.com "echo 'SSH works!'"
```

---

## Production Server Info

| Setting | Value |
|---------|-------|
| Host | `rd.hhivp.com` |
| SSH User | `hhivp` |
| Bot Path | `/opt/tg-modern-bot` |
| Container Name | `hhivp-bot-app-prod` |
| Webhook Port | 8083 (external) → 8080 (internal) |
| Compose File | `docker-compose.prod.yml` |

---

## Common Scenarios

### Scenario 1: New Feature Development
```bash
# Develop locally
make dev

# Test changes
# ...

# Deploy to production
./deploy.sh full
```

### Scenario 2: Bug Fix
```bash
# Fix bug
vim app/...

# Test locally
make dev-restart

# Deploy
git add . && git commit -m "Fix bug"
./deploy.sh full
```

### Scenario 3: Configuration Change
```bash
# Update .env on server manually
ssh hhivp@rd.hhivp.com
vim /opt/tg-modern-bot/.env

# Restart bot (no rebuild needed)
./deploy.sh restart
```

### Scenario 4: Check if Bot is Working
```bash
# Quick status check
./deploy.sh status

# View recent logs
./deploy.sh logs --tail 50

# Real-time logs
ssh hhivp@rd.hhivp.com "docker logs -f hhivp-bot-app-prod"
```

---

## Troubleshooting

### Bot not starting after deployment
```bash
# Check logs for errors
./deploy.sh logs --tail 100

# Check container status
./deploy.sh status

# Restart if needed
./deploy.sh restart
```

### SSH connection issues
```bash
# Test SSH connection
ssh hhivp@rd.hhivp.com "echo 'test'"

# Use password if SSH key not working
# (then run ssh-copy-id again)
```

### Docker build issues
```bash
# Force clean build
./deploy.sh full --no-cache

# Or manually:
ssh hhivp@rd.hhivp.com
cd /opt/tg-modern-bot
docker-compose -f docker-compose.prod.yml build --no-cache bot
docker-compose -f docker-compose.prod.yml up -d bot
```

### Changes not applied after deployment
```bash
# Ensure you're doing full rebuild, not just restart
./deploy.sh full --no-cache

# Verify code was pulled
./deploy.sh pull
ssh hhivp@rd.hhivp.com "cd /opt/tg-modern-bot && git log -1"
```

---

## Manual Deployment (without script)

If you need to deploy manually:

```bash
# 1. Connect to server
ssh hhivp@rd.hhivp.com

# 2. Navigate to project
cd /opt/tg-modern-bot

# 3. Pull latest code
git pull

# 4. Rebuild Docker image
docker-compose -f docker-compose.prod.yml build --no-cache bot

# 5. Stop and remove old container
docker stop hhivp-bot-app-prod
docker rm hhivp-bot-app-prod

# 6. Start new container
docker-compose -f docker-compose.prod.yml up -d bot

# 7. Check logs
docker logs hhivp-bot-app-prod --tail 50
```

---

## Best Practices

1. **Always commit before deploying**
   ```bash
   git add .
   git commit -m "Description"
   ./deploy.sh full
   ```

2. **Use `--no-cache` after dependency changes**
   ```bash
   ./deploy.sh full --no-cache
   ```

3. **Check logs after deployment**
   ```bash
   ./deploy.sh full
   ./deploy.sh logs
   ```

4. **Test locally before production**
   ```bash
   make dev-restart
   # Test features
   ./deploy.sh full
   ```

5. **Use `quick` for minor fixes only**
   ```bash
   # Only for typos, documentation, etc.
   ./deploy.sh quick
   ```

---

## See Also

- [CLAUDE.md](../CLAUDE.md) - Full development guide
- [README.md](../README.md) - Project overview
- [README_DOCKER.md](../README_DOCKER.md) - Docker development guide
