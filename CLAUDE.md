# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## MCP Tools
**Перед выбором инструмента спроси `mcp-compass`** — он порекомендует оптимальный MCP для задачи.

---

## Session Continuity (READ FIRST!)

### Before Starting Work
```bash
cat docs/ROADMAP.md | grep -A2 "Status:"
git log --oneline -5
make test   # 75 unit tests, must pass
```

### Current Priority (2026-02-07)

**Phases 1-5: COMPLETED**
- [x] Phase 1: Critical Fixes (2026-01-20)
- [x] Phase 2: Architecture Improvements (2026-01-23)
- [x] Phase 3: New Features — Voice, AI Reports, Smart Task Detection (2026-01-23)
- [x] Phase 4: AI Task Detection v2 — assignee picker, dedup, audit, training data (2026-02-06)
- [x] Phase 5: Testing Framework — pytest (95 tests), /diag, /ai_quality commands (2026-02-07)

**Full details:** [`docs/ROADMAP.md`](docs/ROADMAP.md)

### After Completing Work
```bash
make test   # Must pass before commit
git add -A && git commit -m "fix(scope): description"
./deploy.sh full  # runs tests → push → pull → build → rebuild
```

### Commit Convention
```
fix(webhook): Remove error details from response
feat(n8n): Add voice transcription webhook
refactor(services): Implement dependency injection
docs: Update roadmap after Phase 1
```

---

## Essential Commands

```bash
# Local dev
make dev                          # Start database + bot
make dev-restart                  # Restart bot (FAST, auto-reload)

# Docker dev (code baked into image, NOT mounted)
make bot-rebuild-clean            # Rebuild after code changes (REQUIRED!)
make full-rebuild-clean           # Rebuild full stack

# Monitoring
make bot-logs                     # View bot logs
make bot-status                   # Check status
make db-shell                     # PostgreSQL console

# Testing (pytest — 95 tests total)
make test              # Unit tests only (75 tests, fast)
make test-all          # All + coverage report
make test-integration  # Integration tests (20 tests)

# Production
./deploy.sh full                  # test + push + pull + build + rebuild + logs
./deploy.sh quick                 # push + pull + restart + logs
./deploy.sh test                  # Run pytest locally (gates deploy)
./deploy.sh diag                  # Remote health check
./deploy.sh logs                  # View production logs
```

**Docker gotcha:** `docker-compose restart` does NOT apply code changes! Must use `make bot-rebuild-clean` or `docker-compose build && docker-compose up -d --force-recreate`.

---

## Module Status Dashboard

| Module | Status | Location | Docs |
|--------|--------|----------|------|
| **Task Reports** | PRODUCTION | `app/modules/task_reports/` | [`task-reports-guide`](docs/guides/task-reports-guide.md) |
| **Support Requests** | PRODUCTION | `app/modules/chat_support/` | [`support-requests-guide`](docs/guides/support-requests-guide.md) |
| **Voice Transcription** | PRODUCTION | `app/handlers/voice_transcription.py` | [`modules-reference`](docs/claude/modules-reference.md) |
| **Daily Tasks** | PRODUCTION | `app/modules/daily_tasks/` | Email → Plane.so automation |
| **Work Journal** | PRODUCTION | `app/modules/work_journal/` | Work entries → Google Sheets |
| **AI Assistant** | PRODUCTION | `app/modules/ai_assistant/` | Smart Task Detection v2 |
| **Chat Monitor** | PRODUCTION | `app/modules/chat_monitor/` | Persistent context + Problems |
| **Chat AI Analysis** | PRODUCTION | `app/services/` | Summary + Problem detection |
| **AI Callbacks** | PRODUCTION | `app/handlers/ai_callbacks.py` | Dedup, assignee picker, task creation |
| **Plane Audit** | PRODUCTION | `app/handlers/plane_audit.py` | `/plane_audit` — deep project analysis |
| **Plane Analysis** | PRODUCTION | `app/handlers/plane_analysis.py` | `/plane_status` — AI status report |
| **AI Training Export** | PRODUCTION | `app/handlers/ai_export.py` | `/ai_export` — training data export |
| **Diagnostics** | PRODUCTION | `app/handlers/diagnostics.py` | `/diag` — system health checks |
| **AI Quality** | PRODUCTION | `app/handlers/ai_quality.py` | `/ai_quality` — detection metrics |

**Detailed module docs:** [`docs/claude/modules-reference.md`](docs/claude/modules-reference.md)

---

## Known Issues & Technical Debt

> **Full details:** [`docs/ROADMAP.md`](docs/ROADMAP.md)

### Critical

| Issue | File | Impact |
|-------|------|--------|
| Event Bus memory leak | `event_bus.py:135` | ~360 MB/month |
| Webhook exposes errors | `server.py:355` | Stack trace leak |
| Webhook verification optional | `server.py:65` | Spoofed webhooks |
| Google Sheets blocking | `google_sheets.py:49` | 1-5s event loop block |
| aiohttp new session/request | `n8n_integration_service.py:104` | 3-5x slower |

### Architecture

| Issue | Solution |
|-------|----------|
| Global singletons | Dependency Injection |
| Hardcoded Telegram IDs (`task_reports_service.py:28-100`) | Move to database |
| N+1 queries | `selectinload()` |
| No rate limiting | Add middleware |
| DB pool size=5 | Increase to 20 |

---

## Architecture Overview

### Hybrid Structure

```
app/
├── handlers/          # Simple handlers (START HERE for new features)
├── modules/           # Complex modular features (FSM, isolation)
│   ├── task_reports/  # Client reporting (PRODUCTION)
│   ├── daily_tasks/   # Email → Plane.so (admin only)
│   ├── work_journal/  # Work entries with state management
│   └── chat_support/  # Support requests
├── services/          # Business logic
├── database/          # SQLAlchemy models + Alembic
├── middleware/         # Request processing
├── integrations/      # External APIs (Plane, n8n)
├── core/              # Enterprise v3.0 (events, plugins, AI)
└── utils/             # Helpers and formatters
```

### Critical Router Loading Order

**MUST be maintained** in `app/main.py:244-264`:
1. `start.router` — Common commands (/start, /help)
2. `daily_tasks_router` — Email processing (admin-only, FIRST priority)
3. `task_reports_router` — Client reporting (state-based)
4. `work_journal_router` — Work entries (state-based)
5. `google_sheets_sync.router` — Integration hooks

**Order matters!** Daily Tasks email filter must be first to prevent conflicts.

### Module Isolation

Each module MUST have filters in `filters.py` to prevent message conflicts. Test with `test_modules_isolation.py`.

### Middleware Stack (`app/main.py:165-181`)

| Order | Middleware | Purpose |
|-------|-----------|---------|
| 1 | DatabaseSessionMiddleware | Creates async DB session |
| 2 | PerformanceMiddleware | Request timing |
| 3 | LoggingMiddleware | Request/response logging |
| 4 | GroupMonitoringMiddleware | Group chat tracking |
| 5 | AuthMiddleware | User authorization |

### Key Services

| Service | File | Purpose |
|---------|------|---------|
| TaskReportsService | `task_reports_service.py` | CRUD + Plane autofill (lines 254-459) |
| DailyTasksService | `daily_tasks_service.py` | Email → Plane, scheduled notifications |
| WorkJournalService | `work_journal_service.py` | CRUD, company/executor mgmt, n8n sync |
| UserTasksCacheService | `user_tasks_cache_service.py` | Plane tasks cache per user |

### Database

**Stack:** PostgreSQL + Redis, SQLAlchemy async + Alembic

**Models:** `models.py` (BotUser), `task_reports_models.py`, `daily_tasks_models.py`, `user_tasks_models.py`, `work_journal_models.py`, `chat_ai_models.py`

**Migrations:** `alembic/versions/` → `alembic upgrade head`

---

## n8n Integration

- **URL:** https://n8n.hhivp.com | **API Key:** `.env` as `N8N_API_KEY`

### Active Bot Workflows

| ID | Workflow | Description |
|----|----------|-------------|
| `lrn3RNMYCeJlvad9` | TG bot → Google Sheets | Bot sends task reports → n8n → Sheets |
| `FJLZaE4hG0JoFH6f` | Plane → Bot (legacy) | TODO: Replace with direct Plane webhook |

### Webhook Endpoints

| Endpoint | Source | Description |
|----------|--------|-------------|
| `POST /webhooks/task-completed` | n8n (legacy) | Task reports |
| `POST /webhooks/plane-direct` | Plane (NEW) | Direct Plane webhooks |
| `POST /webhooks/ai/task-result` | n8n AI | Task detection result |
| `POST /webhooks/ai/voice-result` | n8n AI | Voice report result |
| `GET /health` | Any | Health check |

**Config:** `N8N_URL`, `N8N_WEBHOOK_SECRET`, `AI_TASK_DETECTION_ENABLED` in `.env`

**Full docs:** [`n8n-workflows/README.md`](n8n-workflows/README.md), [`docs/guides/ai-integration-guide.md`](docs/guides/ai-integration-guide.md)

---

## Security & Credentials

- **SECRETS.md** — Production credentials (NEVER commit, in .gitignore)
- **.env** — Local config (NEVER commit)
- **.env.example** — Template (safe to commit)

### Production

| Service | Details |
|---------|---------|
| Server | `ssh hhivp@rd.hhivp.com` (alias: `ssh rd`), bot at `/home/hhivp/tg-bot-prod/` |
| Bot webhook | Port **8083** (ext) → 8080 (int) |
| n8n | https://n8n.hhivp.com |
| Plane.so | https://plane.hhivp.com |
| TG Group | `-1001682373643` (Topic: 2231 for Plane) |

### Infrastructure (hhivp-devops)

Бот работает на инфраструктуре HHIVP. Документация инфраструктуры — в отдельном репозитории.

| Ресурс | URL / Расположение | Назначение |
|--------|---------------------|------------|
| **hhivp-devops repo** | `~/Projects/hhivp-devops` (GitHub: `zarudesu/hhivp_devops`) | Документация инфраструктуры, inventory, credentials |
| **Server docs** | `hhivp-devops/infrastructure/servers/rd.hhivp.com.md` | Полное описание rd.hhivp.com (Docker host бота) |
| **Monitoring** | https://monitoring.hhivp.com | Grafana + Prometheus (метрики сервера и контейнеров) |
| **Logs** | Loki через Grafana | `{host="rd.hhivp.com"}` — логи контейнеров через Promtail |
| **Uptime** | https://kuma.hhivp.com | Uptime Kuma (мониторинг доступности сервисов) |
| **Zabbix** | https://45.10.53.208 | Системный мониторинг (CPU, RAM, disk) |
| **DNS** | `hhivp-devops/dns/dnsconfig.js` | DNS записи n8n.hhivp.com, plane.hhivp.com и др. |
| **Credentials** | `hhivp-devops/.env.servers` | Пароли серверов, API ключи Grafana/Zabbix/n8n |
| **SSH ключ** | `~/.ssh/id_ed25519_hhivp` | Доступ к rd.hhivp.com и остальным серверам HHIVP |

**Сетевая топология на rd.hhivp.com:**
```
Internet → nginx (443) → /bot/ → localhost:8083 → telegram-bot-app:8080
                        → /     → n8n:5678
Plane.so → n8n webhook → n8n workflow → HTTP POST → localhost:8080/webhooks/task-completed
```

**Важно:** n8n и бот в **разных Docker networks**. Для webhook-вызовов между ними используется IP хоста `45.10.53.234`, а не имя контейнера.

---

## Debugging

| Problem | Solution |
|---------|----------|
| Bot not responding | `make bot-logs` |
| DB won't connect | `make db-up && make db-shell` |
| Code changes not applied (Docker) | `make bot-rebuild-clean` (NOT `restart`!) |
| Email not captured by daily_tasks | Check `IsAdminEmailFilter`, verify admin ID, check router order |
| Text captured by wrong module | Check state filters in `filters.py`, verify router order in `main.py` |
| Webhook not working | `make bot-status`, check n8n workflow, `make bot-logs \| grep webhook` |

---

## Testing

```bash
# pytest (recommended — run before every commit/deploy)
python3 -m pytest tests/unit/ -v --tb=short           # 75 unit tests
python3 -m pytest tests/integration/ -v --tb=short     # 20 integration tests
python3 -m pytest tests/ -v --cov=app --cov-report=term-missing  # all + coverage

# Makefile shortcuts
make test              # Unit tests only (fast)
make test-all          # All tests + coverage
make test-integration  # Integration tests only
make test-coverage     # HTML coverage report

# deploy.sh integration
./deploy.sh test       # Run pytest locally (gates deployment)
./deploy.sh full       # Tests → push → pull → build → rebuild
./deploy.sh diag       # Remote health check (curl + container status)
```

**Test infrastructure:** `pyproject.toml` (config), `tests/conftest.py` (fixtures, mocks), `requirements-dev.txt` (dev deps)

**Legacy tests:** 32 old ad-hoc scripts moved to `tests/legacy/` — not included in pytest runs

---

## Development Guide

**Code examples for adding commands, modules, DB models, config:** [`docs/claude/development-guide.md`](docs/claude/development-guide.md)

---

## References

### Key Files
- `app/main.py:244-264` — Router loading order (CRITICAL)
- `app/main.py:165-181` — Middleware stack
- `app/config.py` — Configuration & settings
- `app/webhooks/server.py` — Webhook endpoints
- `app/services/task_reports_service.py:254-459` — Task Reports autofill
- `bot_manager.sh` — Bot process management

### Documentation Index
| File | Purpose |
|------|---------|
| [`TESTING_CHECKLIST.md`](TESTING_CHECKLIST.md) | pytest guide, /diag, /ai_quality, troubleshooting |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Technical debt & roadmap (Phases 1-5) |
| [`docs/claude/modules-reference.md`](docs/claude/modules-reference.md) | Detailed module descriptions |
| [`docs/claude/development-guide.md`](docs/claude/development-guide.md) | Code examples & patterns |
| [`docs/guides/task-reports-guide.md`](docs/guides/task-reports-guide.md) | Task Reports module |
| [`docs/guides/support-requests-guide.md`](docs/guides/support-requests-guide.md) | Support module |
| [`docs/guides/ai-integration-guide.md`](docs/guides/ai-integration-guide.md) | AI via n8n |
| [`n8n-workflows/README.md`](n8n-workflows/README.md) | n8n workflows setup |
| [`docs/DEPLOYMENT_PRODUCTION.md`](docs/DEPLOYMENT_PRODUCTION.md) | Production deploy на rd.hhivp.com |

### Cross-repo (hhivp-devops)
| File | Purpose |
|------|---------|
| `~/Projects/hhivp-devops/CLAUDE.md` | Общий контекст инфраструктуры, SSH доступ |
| `~/Projects/hhivp-devops/infrastructure/servers/rd.hhivp.com.md` | Server docs (Docker host бота) |
| `~/Projects/hhivp-devops/inventory/credentials-index.md` | Навигация по credentials |
| `~/Projects/hhivp-devops/.env.servers` | Пароли серверов, API ключи |

---

**Last Updated:** 2026-02-07
**Bot Version:** 3.0
**Current Phase:** Phase 5 completed — Testing Framework deployed
