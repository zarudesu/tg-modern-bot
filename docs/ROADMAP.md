# Development Roadmap

> **Purpose:** Track technical debt, planned features, and ensure session continuity.
> **Last Audit:** 2026-01-20
> **Next Review:** After Phase 1 completion

---

## Table of Contents

- [Current State](#current-state)
- [Critical Issues (Phase 1)](#-critical-issues-phase-1)
- [Architecture Improvements (Phase 2)](#-architecture-improvements-phase-2)
- [New Features (Phase 3)](#-new-features-phase-3)
- [n8n Integration Plans](#-n8n-integration-plans)
- [Session Continuity](#-session-continuity)

---

## Current State

### Codebase Metrics (2026-01-20)
- **Files:** 167 Python files
- **LOC:** ~22,000 lines
- **Modules:** 6 production, 2 beta
- **Test Coverage:** ~40% (needs improvement)

### Health Score: 6/10

| Category | Score | Notes |
|----------|-------|-------|
| Functionality | 9/10 | All features work |
| Security | 5/10 | Webhook verification optional, PII in logs |
| Performance | 5/10 | Memory leak, blocking I/O |
| Maintainability | 6/10 | Global singletons, hardcoded mappings |
| Scalability | 4/10 | ~100 concurrent users max |

---

## 🔴 Critical Issues (Phase 1)

**Priority:** Fix within 1-2 days
**Status:** ✅ COMPLETED (2026-01-20)

### Issue #1: Event Bus Memory Leak
- **File:** `app/core/events/event_bus.py:135-138`
- **Problem:** `_event_history` grows unbounded (~360 MB/month)
- **Fix:** Add TTL-based cleanup every hour
```python
async def clear_old_events(self):
    cutoff = datetime.now() - timedelta(hours=1)
    self._event_history = [e for e in self._event_history if e.timestamp > cutoff]
```
- **Status:** [x] FIXED (2026-01-20) - Added TTL cleanup, reduced max_history to 100

### Issue #2: Webhook Error Exposure
- **File:** `app/webhooks/server.py:355-356`
- **Problem:** `str(e)` exposes stack traces to clients
- **Fix:** Return generic error, log details server-side
```python
return web.json_response({'error': 'Internal server error'}, status=500)
bot_logger.error(f"Webhook error: {e}", exc_info=True)
```
- **Status:** [x] FIXED (2026-01-20) - Removed details from error response

### Issue #3: Webhook Signature Verification
- **File:** `app/webhooks/server.py:65-70, 137-187`
- **Problem:** Verification is OPTIONAL (if secret not set, accepts all)
- **Fix:** Make `PLANE_WEBHOOK_SECRET` required
```python
if not webhook_secret:
    raise ValueError("PLANE_WEBHOOK_SECRET environment variable is required!")
```
- **Status:** [x] FIXED (2026-01-20) - Added signature verification to task-completed webhook

### Issue #4: Google Sheets Blocking I/O
- **File:** `app/integrations/google_sheets.py:49-82`
- **Problem:** `gspread` is sync library, blocks event loop 1-5 seconds
- **Fix:** Run in thread pool executor
```python
loop = asyncio.get_event_loop()
await loop.run_in_executor(None, self._sync_authorize)
```
- **Status:** [x] FIXED (2026-01-20) - Wrapped gspread calls in ThreadPoolExecutor

### Issue #5: aiohttp Session Per Request
- **Files:** `app/services/n8n_integration_service.py:104`, `app/core/ai/openai_provider.py:50-56`
- **Problem:** New ClientSession per request = TCP+SSL overhead (3-5x slower)
- **Fix:** Create session once, reuse
```python
class N8nIntegrationService:
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None

    async def get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session:
            await self._session.close()
```
- **Status:** [x] FIXED (2026-01-20) - Implemented session reuse in N8nIntegrationService

---

## 🟠 Architecture Improvements (Phase 2)

**Priority:** 1-2 weeks after Phase 1
**Status:** ✅ COMPLETED (2026-01-23)

### Issue #6: Dependency Injection
- **Problem:** Global singletons (`daily_tasks_service = None`)
- **Impact:** Untestable, initialization order fragile
- **Solution:** Use dependency-injector or FastAPI-style Depends
- **Files to modify:**
  - `app/services/daily_tasks_service.py`
  - `app/services/task_reports_service.py`
  - `app/services/support_requests_service.py`
  - `app/main.py`
- **Status:** [ ] DEFERRED - Low priority, current singleton pattern works

### Issue #7: Hardcoded Telegram Mappings
- **File:** `app/services/task_reports_service.py:28-100`
- **Problem:** 50+ Telegram IDs in source code
- **Solution:** Move to database table `plane_telegram_mappings`
- **Migration needed:** Yes
- **Status:** [x] COMPLETED (2026-01-23)
  - Migration 008: Added short_name, group_handle columns
  - Seeded 37 companies, 15 telegram mappings
  - All utils.py functions now use async DB lookups
  - Admin commands: /list_members, /add_member, /list_companies, /add_company
  - Plane API sync: /sync_plane

### Issue #8: N+1 Query Problem
- **Problem:** `selectinload` imported but never used
- **Files:** All services with relationships
- **Solution:** Add eager loading to common queries
- **Status:** [x] ALREADY FIXED (found 2026-01-20) - Batch fetch implemented

### Issue #9: Rate Limiting Implementation
- **Problem:** Configured in `config.py` but never enforced
- **Solution:** Add rate limiting middleware or decorators
- **Status:** [x] ALREADY IMPLEMENTED - Token bucket in `app/middleware/rate_limit.py`

### Issue #10: Database Pool Size
- **File:** `app/database/database.py:12-20`
- **Current:** `pool_size=5, max_overflow=10`
- **Recommended:** `pool_size=20, max_overflow=20`
- **Status:** [x] COMPLETED (2026-01-23) - Changed to pool_size=20, max_overflow=20

---

## 🟢 New Features (Phase 3)

**Priority:** After Phase 1-2 complete
**Status:** SPECIFICATION

### Feature: Voice Message Processing
- **Description:** Transcribe voice messages via AI, create tasks/reports
- **Flow:**
  ```
  User sends voice → Bot downloads file → Direct Whisper API call →
  Transcription shown → User chooses: Task / Journal / Email-task
  ```
- **Dependencies:** OpenAI API key (whisper-1 model)
- **Status:** [x] IMPLEMENTED (2026-01-23)
- **File:** `app/handlers/voice_transcription.py`
- **Features:**
  - Admin-only (API costs money)
  - Russian language by default
  - 3 action buttons after transcription

### Feature: AI Report Generation
- **Description:** Auto-generate work reports from task data
- **Flow:**
  ```
  Task completed → Collect task data + comments →
  Send to AI for summary → Generate formatted report
  ```
- **Dependencies:** OpenAI/Anthropic API
- **Status:** [ ] Spec needed

### Feature: Smart Task Detection
- **Description:** AI analyzes group messages, suggests task creation
- **Flow:**
  ```
  Message in group → AI analyzes intent →
  If task-like → Suggest /task command with pre-filled data
  ```
- **Dependencies:** AI Assistant module, Chat Monitor
- **Status:** [ ] Spec needed

---

## 🔗 n8n Integration Plans

### Current Integrations

| Workflow | Status | Webhook | Purpose |
|----------|--------|---------|---------|
| Task Completed | ✅ PROD | `/webhooks/task-completed` | Plane → Bot notification |
| Work Journal Sync | ✅ PROD | n8n → Google Sheets | Journal entries to sheets |
| Task Report Sync | ✅ PROD | n8n → Google Sheets | Reports to sheets |

### Planned Integrations

#### Voice Transcription Workflow
```
Trigger: Webhook from bot (voice file URL)
Steps:
1. Download voice file
2. Send to OpenAI Whisper API
3. Return transcription to bot
Webhook URL: /webhooks/voice-transcribe
```

#### AI Report Generation Workflow
```
Trigger: Webhook from bot (task data)
Steps:
1. Collect task title, description, comments
2. Send to OpenAI/Claude for summarization
3. Format as report template
4. Return to bot for user review
Webhook URL: /webhooks/generate-report
```

#### Daily Summary Workflow
```
Trigger: Scheduled (18:00 daily)
Steps:
1. Query completed tasks for day
2. Generate AI summary
3. Send to Telegram group
Webhook URL: /webhooks/daily-summary
```

### n8n Webhook Security Requirements
- All webhooks MUST verify signature
- Use `N8N_WEBHOOK_SECRET` environment variable
- Log all webhook calls with request ID

---

## 📋 Session Continuity

### For New Sessions / Compact Mode

**Before starting work, ALWAYS:**

1. **Check current roadmap status:**
   ```bash
   cat docs/ROADMAP.md | grep "Status:"
   ```

2. **Check recent commits:**
   ```bash
   git log --oneline -10
   ```

3. **Check if tests pass:**
   ```bash
   python3 test_modules_isolation.py
   python3 test_basic.py
   ```

4. **Review current TODO in this file**

### After Completing Work

**ALWAYS update before ending session:**

1. **Update issue status** in this file (mark [x] completed)
2. **Add any new issues** discovered
3. **Commit documentation changes:**
   ```bash
   git add docs/ROADMAP.md CLAUDE.md
   git commit -m "docs: Update roadmap status"
   ```

### Commit Message Convention

```
type(scope): description

Types:
- fix: Bug fix
- feat: New feature
- refactor: Code refactoring
- docs: Documentation
- test: Tests
- perf: Performance
- security: Security fix

Examples:
- fix(webhook): Remove error details from response
- feat(n8n): Add voice transcription webhook
- refactor(services): Implement dependency injection
- docs: Update roadmap after Phase 1
```

### Test Checklist Before Commit

```bash
# Required tests
python3 test_modules_isolation.py  # Module isolation
python3 test_basic.py              # Basic functionality

# If modified specific modules
python3 test_email_fix.py          # Daily tasks
python3 test_task_reports_flow.py  # Task reports

# Format check
make format
make typecheck
```

---

## Changelog

### 2026-01-20: Initial Roadmap
- Created from comprehensive code audit
- Identified 5 critical issues
- Defined 3 development phases
- Added n8n integration plans
- Established session continuity guidelines

---

**Next Actions:**
1. [x] Fix Critical Issue #1 (Event Bus memory leak) - DONE 2026-01-20
2. [x] Fix Critical Issue #2 (Webhook error exposure) - DONE 2026-01-20
3. [x] Fix Critical Issue #3 (Webhook verification) - DONE 2026-01-20
4. [x] Fix Critical Issue #4 (Google Sheets blocking) - DONE 2026-01-20
5. [x] Fix Critical Issue #5 (aiohttp session reuse) - DONE 2026-01-20
6. [x] Run syntax checks - DONE 2026-01-20
7. [x] Deploy to production - DONE 2026-01-20
8. [x] Phase 2: Architecture Improvements - COMPLETED 2026-01-23
   - [x] Issue #7: Telegram mappings → DB
   - [x] Issue #8: N+1 queries (already fixed)
   - [x] Issue #9: Rate limiting (already implemented)
   - [x] Issue #10: DB pool size
   - [ ] Issue #6: DI (deferred - low priority)
9. [x] Phase 3: New Features - IN PROGRESS
   - [x] Voice Message Processing - DONE 2026-01-23
   - [ ] AI Report Generation
   - [ ] Smart Task Detection
