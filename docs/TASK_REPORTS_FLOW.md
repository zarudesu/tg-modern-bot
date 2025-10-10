# Task Reports Flow - Complete Documentation

**Status:** ✅ Production Ready (Optimized)
**Last Updated:** 2025-10-09
**Module:** `app/modules/task_reports/`

## Overview

Task Reports provides automated client reporting when support requests are completed in Plane.so. The system creates comprehensive reports with auto-filled data from Plane, sends them to clients, integrates with Google Sheets, and notifies admins.

---

## Complete Flow

### 1. Task Completion in Plane

**Trigger:** Admin marks Plane task as "Done"

```
Plane.so → n8n workflow → Bot Webhook
```

**n8n Workflow:**
- Detects task status change to "Done"
- Sends POST request to `/webhooks/task-completed`
- Payload includes: task details, who closed it, project info

### 2. Webhook Processing

**File:** `app/webhooks/server.py:137-437`

**What happens:**
1. Bot receives POST from n8n
2. Creates TaskReport in database
3. **Auto-fills data from Plane:**
   - Task number (plane_sequence_id)
   - Task title (task_title)
   - Project name
   - Priority
   - Who closed the task (closed_by_plane_name)
   - Description + all comments → report_text
   - Link to Plane task
   - Client chat info (if task was created from chat)

4. Sends notification to admin who closed the task

**Notification message:**
```
📋 Требуется отчёт о выполненной задаче

Задача: #123
Проект: HarzLabs
Приоритет: High
Исполнители: @username
Описание: [description]
Комментарии: [comments]

[4 buttons: Fill Report | Preview | Approve | Close]
```

### 3. Admin Fills MISSING Fields

**Triggered by:** Admin clicks "📝 Заполнить/Редактировать отчёт"

**File:** `app/modules/task_reports/handlers/creation.py:56-109`

**What happens:**
1. Loads Plane data into FSM state:
   - `plane_project_name` - For company suggestions
   - `plane_assignees` - For workers auto-selection
   - `plane_closed_by` - Fallback for workers

2. Opens metadata collection flow (only MISSING fields):

**Metadata Flow:**

#### Step 1: Duration
**File:** `app/modules/task_reports/metadata/duration.py`

- Shows quick buttons: 30 мин, 1 час, 2 часа, 3 часа, 4 часа
- Option to enter custom duration
- Supports formats: "2h", "2ч", "120m", "2:30"

#### Step 2: Work Type
**File:** `app/modules/task_reports/metadata/travel.py`

- Two options: "🚗 Выезд" or "💻 Удалённо"
- Sets `is_travel` flag

#### Step 3: Company
**File:** `app/modules/task_reports/metadata/company.py`

**Company Mapping** (`utils.py:11-43`):
```python
COMPANY_MAPPING = {
    "HarzLabs": "Харц Лабз",
    "3D.RU": "3Д.РУ",
    "Garden of Health": "Сад Здоровья",
    # ... 15+ companies
}
```

- Auto-suggests company from Plane project (with mapping)
- Shows companies from work_journal database
- Option to enter custom company
- **BUG FIX #3:** Applies mapping (HarzLabs → Харц Лабз)

#### Step 4: Workers
**File:** `app/modules/task_reports/metadata/workers.py`

**Workers Auto-fill:**
1. Resolves Plane assignee UUIDs to display names
2. Uses `PLANE_TO_TELEGRAM_MAP` for username mapping
3. Auto-selects workers from Plane assignees
4. Shows all workers from work_journal database
5. Allows multiple selection

**After all metadata collected:**
- Shows summary with "Preview" button
- **NOT full preview** - just a button!

### 4. Preview

**Triggered by:** Admin clicks "👁️ Предпросмотр отчёта"

**File:** `app/modules/task_reports/handlers/preview.py:24-126`

**Single source of truth for preview display:**

```
👁️ Предпросмотр отчёта

Задача: #123
Клиент: ✅ Есть

МЕТАДАННЫЕ РАБОТЫ:
⏱️ Длительность: 2 часа
🚗 Тип работы: Выезд
🏢 Компания: Харц Лабз
👥 Исполнители: Zardes, Ivan

ОТЧЁТ ДЛЯ КЛИЕНТА:
[report_text from Plane description + comments]

Клиенту будет отправлен ТОЛЬКО текст отчёта (без метаданных)

[Buttons: ✅ Одобрить и отправить | ✏️ Редактировать | ❌ Отменить]
```

**Dynamic buttons:**
- If client exists: "✅ Одобрить и отправить" → `approve_send`
- If no client: "✅ Одобрить (без отправки)" → `approve_only`

### 5. Independent Field Editing

**Triggered by:** Admin clicks "✏️ Редактировать"

**File:** `app/modules/task_reports/handlers/edit.py`

**Edit menu shows:**
```
✏️ Меню редактирования отчёта

Задача: #123

Выберите поле для редактирования:
[📝 Текст отчёта]
[⏱️ Длительность: 2 часа]
[🚗 Тип работы: Выезд]
[🏢 Компания: Харц Лабз]
[👥 Исполнители: Zardes, Ivan]
[◀️ Назад к предпросмотру]
[❌ Отменить]
```

**Field editing** (`metadata/navigation.py:154-294`):
1. Admin clicks field to edit
2. `edit_field` handler sets `editing_mode=True`
3. Opens specific metadata handler (duration, travel, company, workers)
4. After editing → **redirects to preview** (not sequential editing!)
5. `editing_mode` flag ensures return to preview

**"Назад" buttons:**
- `tr_back_to_duration` - Navigate back to duration
- `tr_back_to_work_type` - Navigate back to work type
- `tr_back_to_company` - Navigate back to company
- Present in all metadata keyboards

### 6. Approval and Sending

**Triggered by:** Admin clicks "✅ Одобрить и отправить"

**File:** `app/modules/task_reports/handlers/approval.py:165-342`

**BUG FIX #5:** Complete integration flow (was missing Google Sheets + notifications)

**Complete approval flow:**

#### 6.1. Send to Client
```python
# Lines 202-222
client_message = (
    f"✅ **Ваша заявка #{task_report.plane_sequence_id} выполнена!**\n\n"
    f"**Название:** {task_report.task_title}\n\n"
    f"**Отчёт о выполненной работе:**\n\n{task_report.report_text}"
)

await bot.send_message(
    chat_id=task_report.client_chat_id,
    text=client_message,
    reply_to_message_id=task_report.client_message_id  # ✅ Reply in original chat
)
```

#### 6.2. Create Work Journal Entry
```python
# Lines 255-275
entry = await wj_service.create_work_entry(
    telegram_user_id=callback.from_user.id,
    user_email=user_email,
    work_date=task_report.closed_at.date(),
    company=task_report.company,
    work_duration=task_report.work_duration,
    work_description=task_report.report_text,
    is_travel=task_report.is_travel,
    worker_names=workers_list,  # From JSON
    created_by_user_id=callback.from_user.id,
    created_by_name=creator_name
)

# Link to task report
task_report.work_journal_entry_id = entry.id
```

#### 6.3. Send to Google Sheets via n8n
```python
# Lines 285-303
from ....services.n8n_integration_service import N8nIntegrationService

n8n_service = N8nIntegrationService()
success = await n8n_service.send_with_retry(entry, user_data, session)
```

**Uses SAME service as "создать запись" flow:**
- POST request to n8n webhook
- Payload: entry data (company, duration, workers, etc.)
- 3 retries with exponential backoff
- Updates sync status in database

#### 6.4. Send Group Chat Notification
```python
# Lines 305-328
from ....services.worker_mention_service import WorkerMentionService

mention_service = WorkerMentionService(session, callback.bot)

success, errors = await mention_service.send_work_assignment_notifications(
    entry, creator_name, settings.work_journal_group_chat_id
)
```

**Notification format:**
```
📋 Новая запись в журнале работ

👥 Исполнители: @username1, @username2
🏢 Компания: Харц Лабз
📅 Дата: 08.10.2025
⏱ Время: 2 часа
🚗 Тип: Выезд

📝 Описание:
[report text]

📊 [Link to Google Sheets]

👤 Создал: @admin
```

#### 6.5. Notify Admin
```python
# Lines 330-339
await callback.message.edit_text(
    f"✅ **Отчёт одобрен и отправлен клиенту!**\n\n"
    f"Задача #{task_report.plane_sequence_id} завершена.\n\n"
    f"📋 Отчёт отправлен в чат клиента (reply)\n"
    f"📊 Данные сохранены в Google Sheets\n"
    f"👥 Уведомление отправлено в группу"
)
```

### 7. Close Without Report

**Triggered by:** Admin clicks "❌ Закрыть без отчёта клиенту"

**File:** `app/modules/task_reports/handlers/approval.py:410-467`

**What happens:**
1. Marks TaskReport as cancelled
2. Does NOT create work_journal entry
3. Does NOT send to client
4. Notifies admin with status

**Use cases:**
- Internal tasks (no client notification needed)
- Task cancelled
- Admin decision to skip client notification

---

## Architecture

### Module Structure

```
app/modules/task_reports/
├── __init__.py              # Module exports
├── router.py                # Main router
├── states.py                # FSM states
├── keyboards.py             # All keyboard builders
├── utils.py                 # COMPANY_MAPPING, helpers
├── handlers/
│   ├── __init__.py
│   ├── creation.py          # Fill report flow
│   ├── preview.py           # Preview display (single source of truth)
│   ├── edit.py              # Edit menu
│   └── approval.py          # approve_send, approve_only, close_no_report
└── metadata/
    ├── __init__.py
    ├── duration.py          # Duration selection
    ├── travel.py            # Work type (travel/remote)
    ├── company.py           # Company selection with mapping
    ├── workers.py           # Workers selection with autofill
    └── navigation.py        # Back buttons, edit_field handler
```

### FSM States

**File:** `app/modules/task_reports/states.py`

```python
class TaskReportStates(StatesGroup):
    filling_duration = State()      # Collecting duration
    filling_work_type = State()     # Collecting work type
    filling_company = State()       # Collecting company
    filling_workers = State()       # Collecting workers
    filling_report = State()        # Editing report text
    reviewing_report = State()      # Final review before sending
```

### Key Services

#### TaskReportsService
**File:** `app/services/task_reports_service.py`

**Key methods:**
- `create_task_report_from_webhook()` - Create from n8n POST
- `get_task_report()` - Fetch by ID
- `update_metadata()` - Update duration, company, workers
- `approve_report()` - Mark as approved
- `mark_sent_to_client()` - Update sent status
- `close_without_report()` - Cancel report

**Autofill logic** (lines 254-459):
- `fetch_and_generate_report_from_plane()` - Main autofill method
- Company autofill (lines 315-339) - Uses COMPANY_MAPPING
- Workers autofill (lines 341-423) - Resolves UUIDs, uses PLANE_TO_TELEGRAM_MAP
- Report text generation (lines 425-591) - Combines description + comments

#### N8nIntegrationService
**File:** `app/services/n8n_integration_service.py`

**Used by:** Both task_reports and work_journal modules

**Key methods:**
- `send_with_retry()` - Send work entry to Google Sheets (3 retries)
- `_prepare_webhook_data()` - Format data for n8n
- `test_connection()` - Test n8n webhook

#### WorkerMentionService
**File:** `app/services/worker_mention_service.py`

**Key methods:**
- `send_work_assignment_notifications()` - Send to group chat with mentions
- `format_work_assignment_message()` - Format notification message
- `get_worker_mentions()` - Resolve workers to @usernames

### Database Model

**File:** `app/database/user_tasks_models.py`

```python
class TaskReport(Base):
    __tablename__ = 'task_reports'

    id = Column(Integer, primary_key=True)

    # Plane integration
    plane_issue_id = Column(String, nullable=False)
    plane_sequence_id = Column(Integer)
    plane_project_id = Column(String)
    closed_by_plane_name = Column(String)
    closed_at = Column(DateTime(timezone=True))

    # Task data
    task_title = Column(Text)
    task_description = Column(Text)
    priority = Column(String)

    # Client integration
    client_chat_id = Column(BigInteger)
    client_message_id = Column(Integer)

    # Report content
    report_text = Column(Text)

    # Metadata (filled by admin)
    work_duration = Column(String)
    is_travel = Column(Boolean)
    company = Column(String)
    workers = Column(Text)  # JSON array

    # Links
    work_journal_entry_id = Column(Integer)
    support_request_id = Column(Integer)

    # Status tracking
    is_sent_to_client = Column(Boolean, default=False)
    sent_to_client_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

---

## Configuration

### Environment Variables

```bash
# n8n Integration (Google Sheets)
N8N_WEBHOOK_URL=https://n8n.example.com/webhook/work-journal
N8N_WEBHOOK_SECRET=your_secret_here

# Work Journal Group Chat
WORK_JOURNAL_GROUP_CHAT_ID=-1001234567890

# Google Sheets URL (for notification links)
GOOGLE_SHEETS_URL=https://docs.google.com/spreadsheets/d/...
```

### Company Mapping

**File:** `app/modules/task_reports/utils.py:11-43`

Add new companies:
```python
COMPANY_MAPPING = {
    "Plane Project Name": "Russian Display Name",
    "HarzLabs": "Харц Лабз",
    # ... add more
}
```

### Workers Mapping

**File:** `app/config.py` (or separate config)

```python
PLANE_TO_TELEGRAM_MAP = {
    "plane_user_uuid": "telegram_username",
    # ... add more
}
```

---

## Recent Fixes

### BUG #5: approve_send Missing Google Sheets Integration

**Problem:**
`approve_send` handler was NOT sending data to Google Sheets or notifying admins in group chat.

**Fix:** `app/modules/task_reports/handlers/approval.py:224-328`

Added complete integration:
1. ✅ Create work_journal entry
2. ✅ Send to Google Sheets via n8n (using N8nIntegrationService)
3. ✅ Send group chat notification (using WorkerMentionService)
4. ✅ Update admin notification with all statuses

**Result:** Now `approve_send` works IDENTICALLY to "создать запись" flow from main menu.

### BUG #6: Empty Report Generation for Tasks Without Comments

**Date:** 2025-10-10
**Problem:**
Tasks without comments resulted in empty `report_text` even when task had a title and description.

**Root Cause:**
```python
# app/services/task_reports_service.py:654
if len(report_lines) <= 2:  # Only header + title
    return ""  # No meaningful content
```

When task has:
- Header (always) = 1 line
- Title (exists) = 1 line
- Description (<10 chars or empty) = 0 lines
- Comments (none) = 0 lines

Total = 2 lines, condition `2 <= 2` returned empty string.

**Fix:** `app/services/task_reports_service.py:656`
```python
# Only reject if we have ONLY header (no title) or empty
# Header + title is still meaningful (shows task completion)
if len(report_lines) <= 1:
    bot_logger.warning(
        f"⚠️ Report has only {len(report_lines)} lines (header only), "
        f"returning empty. Lines: {report_lines}"
    )
    return ""  # No meaningful content
```

**Result:** Tasks with title (even without comments or description) now generate valid reports.

### BUG #7: Markdown Parse Error When Editing Report Text

**Date:** 2025-10-10
**Problem:**
When editing report text field, Telegram returned error:
```
Bad Request: can't parse entities: Character '>' is reserved and must be escaped with the preceding '\'
```

**Root Cause:**
```python
# app/modules/task_reports/metadata/navigation.py:197-201
await callback.message.edit_text(
    "📝 <b>Редактирование текста отчёта</b>\n\n"
    "Отправьте новый текст отчёта:",
    # ← MISSING parse_mode="HTML"
)
```

Without `parse_mode`, Telegram interprets `<b>` tags as Markdown V2, where `<` and `>` require escaping.

**Fix:** `app/modules/task_reports/metadata/navigation.py:200`
```python
await callback.message.edit_text(
    "📝 <b>Редактирование текста отчёта</b>\n\n"
    "Отправьте новый текст отчёта:",
    parse_mode="HTML"  # ✅ Added
)
```

**Result:** Text editing now works without parse errors. Consistent with other metadata fields (duration, work_type, company, workers all have `parse_mode="HTML"`).

---

## Performance Optimizations

### Webhook Processing Speed

**Before Optimization:** ~13+ seconds
**After Optimization:** ~1-2 seconds

### Optimization 1: Removed Duplicate Plane API Calls

**File:** `app/webhooks/server.py:201-260`
**Commit:** `e072ee2`
**Date:** 2025-10-09

**Problem:**
Webhook handler made duplicate Plane API calls that were already executed in `create_task_report_from_webhook()`:
- `get_issue_details()` - duplicate (line 201)
- `get_issue_comments()` - duplicate (line 213)
- `get_all_projects()` - duplicate (line 226)

**Solution:**
```python
# ✅ USE DATA FROM task_report (already fetched in create_task_report_from_webhook)
# No duplicate Plane API calls needed - all data is in task_report

# Project name (from task_report.company - already mapped via COMPANY_MAPPING)
project_line = ""
if task_report.company:
    project_line = f"**Проект:** {escape_md(task_report.company)}\n"

# Workers/Assignees (from task_report.workers - already auto-filled)
assignees_line = ""
if task_report.workers:
    try:
        workers = json.loads(task_report.workers)
        if isinstance(workers, list) and workers:
            workers_text = ", ".join(workers)
            assignees_line = f"**Исполнители:** {escape_md(workers_text)}\n"
    except:
        pass

# Report text preview (if auto-generated)
report_preview = ""
if task_report.report_text and len(task_report.report_text.strip()) > 50:
    report_text = task_report.report_text.strip()
    if len(report_text) > 200:
        report_text = report_text[:197] + "..."
    report_preview = f"\n**📝 Отчёт \\(preview\\):**\n_{escape_md(report_text)}_\n"
```

**Result:** Reduced API calls from 5-8 to 2-5 per webhook

### Optimization 2: Workspace Members Single Project Fetch

**File:** `app/integrations/plane/users.py:36-44`
**Commit:** `9e3d2b1`
**Date:** 2025-10-09

**Problem:**
`get_workspace_members()` iterated through ALL projects (26 projects) to collect unique members:
- Made 26 API requests (`/projects/{id}/members/`)
- Took ~11 seconds (26 × ~400ms per request)
- Caused n8n webhook timeout (typical timeout: 10-15 seconds)

**Previous Code:**
```python
for project in projects:  # ← 26 projects!
    endpoint = f"/api/v1/workspaces/{workspace}/projects/{project.id}/members/"
    data = await self.client.get(session, endpoint)
    # ... process members
```

**Optimized Code:**
```python
# OPTIMIZATION: All projects have same members, fetch from first project only
bot_logger.info(f"📋 Found {len(projects)} projects, fetching members from FIRST project only (optimization)")

# Try only FIRST project (members are same across all projects)
for project in projects[:1]:  # ← ONLY FIRST PROJECT
    endpoint = f"/api/v1/workspaces/{workspace}/projects/{project.id}/members/"
    data = await self.client.get(session, endpoint)
    # ... process members
```

**Rationale:**
Per user feedback: "У нас одинаковые участники во всех проектах" (We have the same members in all projects)

**Result:**
- **26 API calls → 1 API call**
- **~11 seconds → ~500ms** (22x faster)
- Webhook completes in <3 seconds (no more n8n timeouts)

### Infrastructure Configuration

**Webhook Server:**
- Port: `8083:8080` (container:host)
- Reason: Ports 8080-8082 used by NetBox and other services
- Location: `docker-compose.prod.yml:45-46`

**Nginx Reverse Proxy:**
- Domain: `https://n8n.hhivp.com`
- Path: `/bot/` → `http://127.0.0.1:8083/`
- Config: `/etc/nginx/sites-available/n8n.hhivp.com`

```nginx
# Bot webhooks proxy
location /bot/ {
    proxy_pass http://127.0.0.1:8083/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    proxy_read_timeout 60;
    proxy_connect_timeout 60;
    proxy_send_timeout 60;
}
```

**n8n Webhook URL:**
```
https://n8n.hhivp.com/bot/webhooks/task-completed
```

**Benefits:**
- ✅ No Docker network complexity (n8n-ready_default not needed)
- ✅ Global nginx handles SSL/TLS
- ✅ Standard port 443 (HTTPS)
- ✅ Easy to monitor and debug
- ✅ Can add rate limiting, IP filtering, etc. at nginx level

### Performance Testing Results

**Test Webhook Payload:**
```json
{
  "plane_issue_id": "test-999",
  "plane_sequence_id": 999,
  "plane_project_id": "4df07960-f664-4aba-a757-94a1106c9bae",
  "task_title": "TEST Webhook Optimization",
  "task_description": "Testing optimized webhook",
  "closed_by": {
    "display_name": "Zardes",
    "first_name": "Konstantin",
    "email": "zarudesu@gmail.com"
  },
  "closed_at": "2025-10-09T22:00:00Z"
}
```

**Before Optimization:**
```
Total time: ~13+ seconds
- Webhook received: 21:18:11
- get_workspace_members() started: 21:18:13
- get_workspace_members() completed: 21:18:24 (11 seconds!)
- Notification sent: 21:18:24
Result: n8n timeout error
```

**After Optimization:**
```
Total time: ~1.05 seconds
HTTP Status: 200
Response: {"status": "processed", "task_report_id": 3, "plane_sequence_id": 999}

Breakdown:
- Webhook received: 22:36:57
- TaskReport created: 22:36:57 (instant)
- Plane data fetched: 22:36:57-22:36:58 (~1s)
- Notification sent: 22:36:58
Result: ✅ Success, no timeout
```

**Performance Gain:**
- **13x faster** (13s → 1s)
- **n8n timeout eliminated**
- **Plane API rate limiting avoided** (26 calls → 1 call)

---

## Testing

### Manual Testing Checklist

1. **Webhook Flow:**
   - [ ] Move Plane task to "Done"
   - [ ] Verify TaskReport created in database
   - [ ] Verify admin receives notification

2. **Autofill:**
   - [ ] Check task number, title, project autofilled
   - [ ] Check description + comments → report_text
   - [ ] Check company mapping applied
   - [ ] Check workers auto-selected from Plane assignees

3. **Metadata Collection:**
   - [ ] Fill duration → verify saved
   - [ ] Select work type → verify saved
   - [ ] Select company → verify mapping applied
   - [ ] Select workers → verify JSON saved

4. **Preview:**
   - [ ] Click "Preview" button → see full preview
   - [ ] Verify all metadata displayed
   - [ ] Verify report text shown

5. **Independent Editing:**
   - [ ] Click "Edit" → see edit menu
   - [ ] Edit duration → verify returns to preview (not sequential)
   - [ ] Edit company → verify mapping applied
   - [ ] Edit workers → verify selection saved

6. **Approval:**
   - [ ] Click "Approve and send"
   - [ ] Verify report sent to client (as reply)
   - [ ] Verify work_journal entry created
   - [ ] Verify data in Google Sheets
   - [ ] Verify group chat notification

7. **Close Without Report:**
   - [ ] Click "Close without report"
   - [ ] Verify no client notification
   - [ ] Verify no work_journal entry
   - [ ] Verify TaskReport marked as cancelled

### Automated Tests

**File:** `test_task_reports_flow.py`

```bash
python3 test_task_reports_flow.py
```

Tests:
- ✅ Preview button flow
- ✅ Independent field editing
- ✅ Workers autofill from Plane
- ✅ Preview handler structure

---

## Troubleshooting

### Report not sent to client

**Check:**
1. `task_report.client_chat_id` is set
2. `task_report.client_message_id` is set (for reply)
3. Bot has access to client chat
4. Client hasn't blocked bot

### Google Sheets data missing

**Check:**
1. `N8N_WEBHOOK_URL` configured in .env
2. n8n workflow is active
3. Check bot logs for "Successfully sent entry X to n8n"
4. Check n8n workflow execution logs

### Workers not auto-selected

**Check:**
1. Plane assignees UUIDs returned from API
2. `plane_assignees` in FSM state
3. Workspace members loaded successfully
4. PLANE_TO_TELEGRAM_MAP configured

### Company mapping not working

**Check:**
1. Plane project name in COMPANY_MAPPING
2. `map_company_name()` called in company.py:42
3. Check bot logs for "🔄 Mapped company: 'X' → 'Y'"

---

## Future Enhancements

1. **Email notifications** to clients (in addition to Telegram)
2. **Report templates** for common task types
3. **Auto-approval** for simple tasks (configurable)
4. **Report statistics** dashboard
5. **Custom fields** per company/project

---

## See Also

- `TASK_REPORTS_FIXES.md` - Recent bug fixes
- `app/webhooks/server.py` - Webhook implementation
- `app/services/task_reports_service.py` - Business logic
- `app/services/n8n_integration_service.py` - Google Sheets integration
- `app/services/worker_mention_service.py` - Group notifications
