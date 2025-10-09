# Task Reports Module - Complete Guide

## 📊 Status: PRODUCTION READY

**Last Updated:** 2025-10-08
**Module Location:** `app/modules/task_reports/`
**Related Documentation:**
- `docs/TASK_REPORTS_FLOW.md` - Complete flow description
- `TASK_REPORTS_FIXES.md` - Bug fixes history

---

## 🎯 Purpose

Automated client reporting system when support tasks are completed in Plane.so. When admin marks task as "Done" in Plane, bot guides admin through creating a client report and sends it to the client chat.

---

## 🔄 Complete Flow

### 1. Webhook Trigger
```
Admin marks task as "Done" in Plane
  ↓
n8n detects status change
  ↓
POST to bot webhook /api/webhooks/plane/task-completed
```

### 2. Bot Creates TaskReport (Autofilled)
Bot automatically fills from Plane data:
- ✅ Task number, title, project, priority
- ✅ Who closed the task (`closed_by_plane_name`)
- ✅ Client chat info (if task was created from chat)
- ✅ Description and all comments → `report_text`
- ✅ Link to Plane task

### 3. Admin Notification
Bot sends to admin:
```
📋 Требуется отчёт о выполненной задаче

[Task Details Preview Button]
[Fill Report Button]
```

### 4. Admin Fills Missing Fields
Admin only fills **4 required fields**:
- ⏱️ **Duration** - Time spent on task
- 🚗 **Travel** - Travel time (if any)
- 🏢 **Company** - Client company (uses COMPANY_MAPPING)
- 👥 **Workers** - Who worked on task (auto-suggested from Plane assignees)

### 5. Admin Approves → Full Integration
When admin clicks "Approve & Send", bot executes:
- ✅ Send report to client (reply in original chat)
- ✅ Create work_journal entry
- ✅ Send to Google Sheets via n8n (same as "создать запись")
- ✅ Notify admins in group chat

---

## 📁 Module Structure

```
app/modules/task_reports/
├── handlers/
│   ├── creation.py       # Fill report flow, start filling process
│   ├── preview.py        # Single source of truth for preview rendering
│   ├── edit.py           # Edit menu, field editing
│   └── approval.py       # approve_send, close_no_report actions
│
├── metadata/              # Individual field handlers
│   ├── duration.py       # Duration input & validation
│   ├── travel.py         # Travel time input & validation
│   ├── company.py        # Company selection (uses COMPANY_MAPPING)
│   ├── workers.py        # Workers selection (auto-fill from Plane)
│   └── navigation.py     # Back buttons & edit_field callback
│
├── keyboards.py          # All keyboard builders (inline keyboards)
├── utils.py              # COMPANY_MAPPING, escape_markdown_v2, parse_report_id_safely
├── states.py             # FSM states (TaskReportStates)
└── router.py             # Main router (loads all sub-routers)
```

---

## 🏗️ Architecture Highlights

### Independent Field Editing
Each field can be edited independently without sequential flow:
```python
Edit Report Menu
├─ Edit Duration      → duration.py
├─ Edit Travel        → travel.py
├─ Edit Company       → company.py
├─ Edit Workers       → workers.py
└─ Back to Preview    → preview.py
```

### Preview Button Architecture
Shows compact preview button → click → full detailed preview:
```python
# In handlers/preview.py
async def show_task_details_callback(...)
    # Single source of truth for preview rendering
    # Called from: creation, edit, navigation
```

### Company Mapping
15+ companies mapped from Plane projects to Russian names:
```python
# In utils.py
COMPANY_MAPPING = {
    "HarzLabs": "Харц Лабз",
    "SomeCorp": "Компания LLC",
    # ... 15+ mappings
}
```

### Workers Autofill
Resolves Plane UUIDs to Telegram usernames:
```python
# In metadata/workers.py
async def autofill_workers_from_plane(report_id, plane_assignees)
    # Resolves UUIDs → @username
    # Auto-suggests in worker selection
```

---

## 🔧 Key Services Used

### TaskReportsService (`app/services/task_reports_service.py`)
**Lines 254-459:** CRUD + autofill logic

Key methods:
```python
async def create_report(webhook_data)
    # Creates TaskReport from Plane webhook

async def autofill_from_plane(report_id)
    # Fills data from Plane API

async def update_report_field(report_id, field, value)
    # Updates individual field

async def complete_report(report_id)
    # Marks report as completed
```

### N8nIntegrationService (`app/services/n8n_integration_service.py`)
Google Sheets sync (same as work_journal):
```python
async def send_to_google_sheets(work_journal_entry)
    # POST to n8n webhook → Google Sheets
```

### WorkerMentionService (`app/services/worker_mention_service.py`)
Group chat notifications:
```python
async def notify_group(task_info, workers)
    # Sends notification to Telegram group
```

---

## 🐛 Recent Fixes

**BUG #5** (2025-10-08): `approve_send` Google Sheets Integration
**Fixed in:** `app/modules/task_reports/handlers/approval.py`

**Issue:** On approve_send, bot was NOT creating work_journal entry or sending to Google Sheets

**Solution:**
```python
# approval.py:XX - Added work_journal creation
work_entry = await work_journal_service.create_entry(...)
await n8n_service.send_to_google_sheets(work_entry)
await worker_mention_service.notify_group(...)
```

**See:** `TASK_REPORTS_FIXES.md` for complete fix history

---

## 🧪 Testing

### Test Script: Create Test Task with Comments & Assignees

**Location:** `/tmp/create_test_task.py`

This script creates a realistic test task in Plane with:
- ✅ Full description (HTML format)
- ✅ 2 test comments (Russian text)
- ✅ Auto-assigned to your user
- ✅ High priority
- ✅ Ready to close → test full flow

**Usage:**
```bash
# Set your Plane API token (get from SECRETS.md or .env)
export PLANE_API_TOKEN="plane_api_xxxx"

# Run the script
./venv/bin/python /tmp/create_test_task.py
```

**Expected Output:**
```
📋 Available projects:
   - Project Name (ID: uuid...)

✨ Creating test task in project: Project Name

👥 Looking up your user...
   ✅ Found: Your Name (uuid...)

✅ Task created successfully!
   Issue ID: uuid...
   Sequence: #79
   URL: https://plane.hhivp.com/...

📝 Adding test comments...
   ✅ Comment 1 added: uuid...
   ✅ Comment 2 added: uuid...

📝 Next steps:
   1. Переведи задачу #79 в статус 'Done'
   2. Бот создаст TaskReport и отправит уведомление
   3. Проверь автозаполнение всех полей
   4. Нажми 'Preview' → Edit → Return to preview
```

**Script Features:**
- Auto-fills **description** from template (testing plan)
- Auto-fills **assignees** (finds user by email: zarudesu@gmail.com)
- Adds **2 realistic comments** (work description + details)
- Priority set to **high** for testing

**What to Test After Creation:**

1. **Mark task as Done in Plane UI**

2. **Check bot receives webhook:**
```bash
make bot-logs | grep "task-completed"
```

3. **Verify autofill in Telegram:**
   - Description & comments merged into `report_text`
   - Workers auto-filled from assignees
   - Company auto-filled from project name

4. **Fill missing fields:**
   - Duration: 2 hours
   - Travel: No (remote)
   - Company: (should be pre-filled)
   - Workers: (should be pre-filled)

5. **Verify integrations:**
   - ✅ Client receives report (if chat linked)
   - ✅ Work journal entry created
   - ✅ Google Sheets row added
   - ✅ Group chat notification sent

### Integration Tests
```bash
# Full end-to-end test
python3 test_task_reports_flow.py

# Check webhook endpoint directly
curl -X POST http://localhost:8000/api/webhooks/plane/task-completed \
  -H "Content-Type: application/json" \
  -d @test_webhook_payload.json
```

---

## ⚙️ Configuration

### Required Environment Variables
```bash
# Plane.so
PLANE_API_URL=https://plane.example.com
PLANE_API_TOKEN=plane_api_xxx
PLANE_WORKSPACE_SLUG=workspace-slug

# n8n Webhook
N8N_WEBHOOK_URL=https://n8n.example.com/webhook/xxx
N8N_WEBHOOK_SECRET=secret_here

# Google Sheets (via n8n)
GOOGLE_SHEETS_ID=spreadsheet_id_here

# Telegram Group
TELEGRAM_GROUP_ID=-1001682373643
TELEGRAM_GROUP_TOPIC_ID=2231
```

### Webhook Setup in n8n

1. **Create workflow:** Plane → Webhook
2. **Trigger:** Plane issue status changed to "Done"
3. **Webhook URL:** `{BOT_URL}/api/webhooks/plane/task-completed`
4. **Method:** POST
5. **Headers:** `X-Webhook-Secret: {N8N_WEBHOOK_SECRET}`

---

## 🚨 Troubleshooting

### Webhook not received
```bash
# Check webhook server is running
make bot-status

# Check n8n workflow is active
# Visit: https://n8n.hhivp.com/workflows

# Check logs
make bot-logs | grep webhook
```

### Report not autofilled
```python
# In task_reports_service.py:254-459
# Check autofill_from_plane() method
# Verify PLANE_API_TOKEN is valid
# Check Plane task has required fields
```

### Google Sheets not syncing
```bash
# Check N8N_WEBHOOK_URL in .env
# Check n8n workflow is active
# Verify work_journal entry was created
make db-shell
SELECT * FROM work_journal_entries ORDER BY created_at DESC LIMIT 1;
```

### Workers not autofilling
```python
# In metadata/workers.py
# Check Plane assignees UUIDs are valid
# Verify users exist in bot database
# Check worker_mention_service.py mapping
```

---

## 🔜 Future Improvements

- [ ] Auto-detect duration from Plane time tracking
- [ ] Support multiple client chats per task
- [ ] Add report templates for different task types
- [ ] Export reports to PDF
- [ ] Analytics dashboard for completed reports

---

## 📚 Related Documentation

- `docs/TASK_REPORTS_FLOW.md` - Detailed flow diagrams
- `TASK_REPORTS_FIXES.md` - Bug fixes history
- `app/webhooks/server.py` - Webhook endpoints
- `app/services/task_reports_service.py` - Core service

---

**Questions?** Check logs: `make bot-logs`
**Report bugs:** Create issue with `[Task Reports]` prefix
