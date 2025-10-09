# Task Reports Flow - Complete Documentation

**Status:** ✅ Production Ready
**Last Updated:** 2025-10-08
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
