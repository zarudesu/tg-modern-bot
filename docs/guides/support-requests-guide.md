# Support Requests System - Complete Guide

**Status:** ✅ PRODUCTION READY (loaded, not configured yet)
**Module:** `app/modules/chat_support/`
**Database:** `chat_plane_mappings`, `support_requests`
**Last Updated:** 2025-10-22

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Architecture](#-architecture)
- [Setup Guide](#-setup-guide)
- [User Flow](#-user-flow)
- [Admin Commands](#-admin-commands)
- [Database Schema](#-database-schema)
- [Integration with Plane](#-integration-with-plane)
- [Troubleshooting](#-troubleshooting)

---

## 🎯 Overview

**Purpose:** Allow users to create support requests directly from Telegram group chats, which automatically become tasks in Plane.so

**Key Features:**
- ✅ Simple user flow: `/request` → type problem → done
- ✅ Auto-creates tasks in Plane with full user context
- ✅ Notifies admins about new requests
- ✅ Maps group chats to specific Plane projects
- ✅ FSM-based (Finite State Machine) for reliable state tracking

**Current Status in Production:**
- ✅ Module loaded and active (main.py:273-275)
- ❌ No chat mappings configured yet
- ❌ No requests created yet
- ⚠️ Needs setup before users can create requests

---

## 🏗️ Architecture

### Two Support Request Modules

**1. `chat_support` - ACTIVE** ✅ (Currently used)
- Location: `app/modules/chat_support/`
- Flow: Simple FSM-based, ForceReply
- Command: `/request`
- Status: Loaded in main.py, ready to use

**2. `support_requests` - INACTIVE** ❌ (Alternative, not loaded)
- Location: `app/modules/support_requests/`
- Flow: Inline buttons, step-by-step (title → description → priority)
- Command: `/new_request`
- Status: Code exists but not loaded in main.py

**Both modules share:**
- Same database models (`support_requests_models.py`)
- Same service layer (`support_requests_service.py`)
- Same Plane.so integration

### Files Structure

```
app/
├── modules/
│   └── chat_support/                    # ✅ ACTIVE MODULE
│       ├── router.py                    # Main router
│       ├── handlers.py                  # /request command + FSM handlers
│       ├── admin_handlers.py            # /setup_chat, /remove_chat, /list_chats
│       └── states.py                    # FSM states (waiting_for_problem)
│
├── services/
│   └── support_requests_service.py      # Business logic (CRUD, Plane integration)
│
└── database/
    └── support_requests_models.py       # ChatPlaneMapping, SupportRequest
```

### Router Loading Order

From `app/main.py:241-280`:

```python
1. start.router                          # Common commands
2. daily_tasks_router                    # Email processing (admin-only)
3. task_reports_router                   # Client reporting (FSM)
4. work_journal_router                   # Work entries (FSM)
5. google_sheets_sync.router             # Integration hooks
6. ai_assistant_router                   # AI features
7. chat_support_router                   # 🎯 Support requests (FSM) - line 273
8. chat_monitor_router                   # Group monitoring (catches all)
```

**Important:** `chat_support` is loaded BEFORE `chat_monitor` to intercept `/request` commands before monitor catches everything.

---

## 🚀 Setup Guide

### Prerequisites

1. ✅ Bot has admin permissions in target group chat
2. ✅ Plane.so API configured (`PLANE_API_TOKEN`, `PLANE_WORKSPACE_SLUG`)
3. ✅ At least one Plane project exists
4. ✅ Admin has correct `ADMIN_USER_IDS` in `.env`

### Step 1: Configure Chat Mapping

**Run in target group chat:**

```
/setup_chat
```

**What happens:**
1. Bot shows list of Plane projects (first 20)
2. Admin clicks on desired project
3. Bot creates `ChatPlaneMapping` in database
4. Users can now use `/request` in this chat

**Example:**

```
Admin: /setup_chat

Bot: 📁 Выберите проект для этого чата:

     [📁 HHIVP Support]
     [📁 HARZL Maintenance]
     [📁 DELTA Development]
     [❌ Отмена]

Admin clicks: "HHIVP Support"

Bot: ✅ Чат настроен!

     💬 Чат: HHIVP Support Group
     📁 Проект: HHIVP Support

     Пользователи могут создавать заявки через /request
```

### Step 2: Verify Configuration

**Check all configured chats:**

```
/list_chats
```

**Output:**

```
📋 Настроенные чаты (1)

1. HHIVP Support Group
   📁 HHIVP Support
```

### Step 3: Users Can Now Create Requests

Users in configured groups can use `/request` (see [User Flow](#-user-flow))

---

## 👥 User Flow

### Creating a Request

**1. User runs command in group chat:**

```
/request
```

**2. Bot replies with ForceReply:**

```
📝 Создание заявки

📁 Проект: HHIVP Support

Опишите проблему ниже:
[Reply field appears with placeholder "Опишите проблему..."]
```

**3. User types problem description:**

```
User: Не работает VPN на сервере rd.hhivp.com, нужна помощь
```

**4. Bot processes request:**

```
✅ Заявка создана!

📋 Номер заявки: #145
📁 Проект: HHIVP Support

Ваша заявка принята и отправлена в обработку.
Администраторы уведомлены.
```

**5. Admin receives notification in private chat:**

```
🔔 Новая заявка #145

👤 От кого: Константин Заруднев
🆔 Telegram ID: 28795547
👤 Username: @zardes
💬 Чат: HHIVP Support Group

📝 Проблема:
Не работает VPN на сервере rd.hhivp.com, нужна помощь

📁 Проект: HHIVP Support

[🔗 Открыть в Plane] (button with link)
```

### FSM State Management

**States defined in `states.py`:**

```python
class SupportRequestStates(StatesGroup):
    waiting_for_problem = State()
```

**Flow:**
1. User runs `/request` → FSM state set to `waiting_for_problem`
2. User sends text → Handler processes only if state is active
3. Request created → FSM state cleared
4. User sends another message → NOT captured (state cleared)

**This ensures:**
- ✅ Only next message after `/request` is captured
- ✅ No conflicts with other modules
- ✅ Clean state management

---

## 🔧 Admin Commands

### `/setup_chat` (Group only)

**Purpose:** Configure group chat for support requests

**Requirements:**
- Must be admin (`ADMIN_USER_IDS`)
- Must run in group chat
- Plane API must be configured

**Flow:**
1. Check if chat already configured
2. Fetch Plane projects (first 20)
3. Show inline keyboard with projects
4. Admin selects → creates mapping

**Database:**
```sql
INSERT INTO chat_plane_mappings (
    chat_id,
    chat_title,
    chat_type,
    plane_project_id,
    plane_project_name,
    created_by,
    is_active
) VALUES (...)
```

### `/remove_chat` (Group only)

**Purpose:** Remove chat mapping (disable support requests)

**Flow:**
1. Check if mapping exists
2. Show confirmation button
3. Admin confirms → set `is_active = false`

**Note:** Does NOT delete mapping, just deactivates it.

### `/list_chats` (Anywhere)

**Purpose:** List all active chat mappings

**Output:**
```
📋 Настроенные чаты (3)

1. HHIVP Support Group
   📁 HHIVP Support

2. HARZL Maintenance Chat
   📁 HARZL Maintenance

3. DELTA Dev Team
   📁 DELTA Development
```

---

## 🗄️ Database Schema

### `chat_plane_mappings`

Maps Telegram chats to Plane projects.

```sql
CREATE TABLE chat_plane_mappings (
    id SERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL UNIQUE,           -- Telegram chat ID
    chat_title VARCHAR(255),                  -- Chat name for reference
    chat_type VARCHAR(50) NOT NULL,           -- group, supergroup, channel

    plane_project_id VARCHAR(100) NOT NULL,   -- Plane project UUID
    plane_project_name VARCHAR(255),          -- Project name for display

    is_active BOOLEAN DEFAULT true,           -- Active/deactivated
    allow_all_users BOOLEAN DEFAULT true,     -- Allow all users or whitelist

    created_by BIGINT NOT NULL,               -- Admin who created
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_chat_plane_mappings_chat_id ON chat_plane_mappings(chat_id);
CREATE INDEX idx_chat_plane_mappings_project ON chat_plane_mappings(plane_project_id);
CREATE INDEX idx_chat_plane_mappings_active ON chat_plane_mappings(is_active);
```

**Example row:**
```
id: 1
chat_id: -1001682373643
chat_title: "HHIVP Support Group"
chat_type: "supergroup"
plane_project_id: "4df07960-f664-4aba-a757-94a1106c9bae"
plane_project_name: "HHIVP Support"
is_active: true
created_by: 28795547
created_at: 2025-10-22 10:30:00
```

### `support_requests`

Stores user support requests.

```sql
CREATE TABLE support_requests (
    id SERIAL PRIMARY KEY,

    -- Origin
    chat_id BIGINT NOT NULL,                  -- FK to chat_plane_mappings
    user_id BIGINT NOT NULL,                  -- Telegram user ID
    user_name VARCHAR(255),                   -- User's display name

    -- Request details
    title TEXT NOT NULL,                      -- Auto-generated from first 50 chars
    description TEXT,                         -- Full problem text + user context
    priority VARCHAR(20) DEFAULT 'medium',    -- urgent, high, medium, low

    -- Plane integration
    plane_project_id VARCHAR(100) NOT NULL,   -- Which project
    plane_issue_id VARCHAR(100),              -- Created issue UUID
    plane_sequence_id INTEGER,                -- Issue number (e.g., #145)

    -- Status tracking
    status VARCHAR(50) DEFAULT 'pending',     -- pending, created, failed, cancelled
    error_message TEXT,                       -- Error if creation failed

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    plane_created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_support_requests_chat_id ON support_requests(chat_id);
CREATE INDEX idx_support_requests_user_id ON support_requests(user_id);
CREATE INDEX idx_support_requests_status ON support_requests(status);
CREATE INDEX idx_support_requests_user_status ON support_requests(user_id, status);
```

**Example row:**
```
id: 1
chat_id: -1001682373643
user_id: 28795547
user_name: "zardes"
title: "Не работает VPN на сервере rd.hhivp.com, нужна..."
description: "**📱 Telegram User Info:**\n- **Full Name:** Константин Заруднев\n..."
priority: "medium"
plane_project_id: "4df07960-f664-4aba-a757-94a1106c9bae"
plane_issue_id: "abc-def-123"
plane_sequence_id: 145
status: "created"
created_at: 2025-10-22 10:35:00
plane_created_at: 2025-10-22 10:35:02
```

---

## 🔗 Integration with Plane

### Request Creation Flow

**File:** `app/modules/chat_support/handlers.py:108-154`

**Step 1: Auto-generate title** (handlers.py:122)
```python
title = problem_text[:50] + ("..." if len(problem_text) > 50 else "")
```

**Step 2: Build rich description with user context** (handlers.py:124-134)
```python
description = (
    f"**📱 Telegram User Info:**\n"
    f"- **Full Name:** {user.full_name}\n"
    f"- **Username:** @{user.username or 'не указан'}\n"
    f"- **User ID:** `{user.id}`\n"
    f"- **Chat:** {message.chat.title}\n"
    f"- **Time:** {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
    f"---\n\n"
    f"**📝 Описание проблемы:**\n\n{problem_text}"
)
```

**Step 3: Create in database** (handlers.py:139-147)
```python
request = await support_requests_service.create_support_request(
    session=session,
    chat_id=chat_id,
    user_id=user_id,
    user_name=username,
    title=title,
    description=description,
    priority="medium"  # Fixed priority for now
)
```

**Step 4: Submit to Plane** (handlers.py:152-154)
```python
success, error_msg, plane_request = await support_requests_service.submit_to_plane(
    session, request.id
)
```

### Plane API Call

**File:** `app/services/support_requests_service.py:152-220`

**Key steps:**
1. Get all workspace members (line 176)
2. Create issue assigned to all admins (line 180-187)
3. Update request with Plane data (line 196-201)
4. Return success + request object

**Plane API payload:**
```python
{
    "name": "Не работает VPN на сервере rd.hhivp.com, нужна...",
    "description": "**📱 Telegram User Info:**\n...",
    "priority": "medium",
    "assignees": ["uuid1", "uuid2", "uuid3"]  # All workspace members
}
```

**Response:**
```python
{
    "id": "abc-def-123",           # plane_issue_id
    "sequence_id": 145,            # plane_sequence_id (HHIVP-145)
    "name": "...",
    "description": "...",
    "project": "4df07960-...",
    ...
}
```

### Admin Notifications

**File:** `app/modules/chat_support/handlers.py:172-200`

**For each admin:**
```python
for admin_id in settings.admin_user_id_list:
    await message.bot.send_message(
        chat_id=admin_id,
        text=(
            f"🔔 **Новая заявка #{plane_request.plane_sequence_id}**\n\n"
            f"{user_info}\n"
            f"📝 **Проблема:**\n{problem_text[:500]}\n\n"
            f"📁 **Проект:** {mapping.plane_project_name}"
        ),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="🔗 Открыть в Plane",
                url=f"https://plane.hhivp.com/hhivp/projects/{project_id}/issues/{issue_id}"
            )
        ]]),
        parse_mode="Markdown"
    )
```

---

## 🐛 Troubleshooting

### Common Issues

**1. "Этот чат не настроен для заявок"**

**Причина:** No `chat_plane_mappings` entry for this chat.

**Решение:**
```
/setup_chat  (run by admin in group chat)
```

**Проверка:**
```sql
SELECT * FROM chat_plane_mappings WHERE chat_id = -1001682373643;
```

---

**2. "Не удалось отправить в Plane"**

**Причина:** Plane API error (network, auth, invalid project)

**Решение:**
1. Check Plane API credentials in `.env`:
   ```
   PLANE_API_URL=https://plane.hhivp.com
   PLANE_API_TOKEN=plane_api_xxxxx
   PLANE_WORKSPACE_SLUG=hhivp
   ```

2. Check project exists:
   ```python
   projects = await plane_api.get_all_projects()
   print([p['name'] for p in projects])
   ```

3. Check bot logs:
   ```bash
   make bot-logs | grep "support_request"
   ```

**Database entry:**
```sql
SELECT * FROM support_requests WHERE status = 'failed';
-- Check error_message column
```

---

**3. Admin not receiving notifications**

**Причина:** Admin ID not in `ADMIN_USER_IDS` or bot blocked by admin

**Решение:**
1. Check `.env`:
   ```
   ADMIN_USER_IDS=28795547,132228544,56994156
   ```

2. Check bot logs:
   ```bash
   make bot-logs | grep "Failed to notify admin"
   ```

3. Admin must start bot first (send `/start` in private chat)

---

**4. User message captured by wrong handler**

**Причина:** FSM state not properly managed or router order wrong

**Решение:**
1. Check FSM state is cleared after processing (handlers.py:212)
2. Verify `chat_support_router` loaded BEFORE `chat_monitor_router` (main.py:273-278)

**Debug:**
```python
bot_logger.info(f"FSM state for user {user_id}: {await state.get_state()}")
```

---

**5. "/request command not working"**

**Причина:** Module not loaded or bot doesn't have permissions

**Решение:**
1. Check module loaded:
   ```bash
   make bot-logs | grep "Chat Support module loaded"
   # Should show: ✅ Chat Support module loaded (simple /request flow)
   ```

2. Check bot has permissions in group (can read messages)

3. Verify command registered:
   ```python
   await bot.get_my_commands()
   # Should include "request" command
   ```

---

## 📊 Statistics & Monitoring

### Get request counts

```sql
-- Total requests
SELECT COUNT(*) FROM support_requests;

-- By status
SELECT status, COUNT(*) FROM support_requests GROUP BY status;

-- By chat
SELECT m.chat_title, COUNT(r.id) as requests
FROM chat_plane_mappings m
LEFT JOIN support_requests r ON m.chat_id = r.chat_id
GROUP BY m.chat_title;

-- Recent requests
SELECT
    sr.id,
    sr.user_name,
    sr.title,
    sr.status,
    sr.plane_sequence_id,
    m.chat_title,
    sr.created_at
FROM support_requests sr
JOIN chat_plane_mappings m ON sr.chat_id = m.chat_id
ORDER BY sr.created_at DESC
LIMIT 20;
```

### Performance monitoring

From bot logs:
```bash
make bot-logs | grep "support_request"
```

**Key metrics:**
- Request creation time (should be < 1s)
- Plane API submission time (should be < 3s)
- FSM state lifecycle

---

## 🔮 Future Improvements

### Potential Enhancements

1. **Priority selection** - Allow users to choose priority (urgent/high/medium/low)
2. **Request editing** - Allow users to edit/cancel pending requests
3. **Status tracking** - Notify user when request status changes in Plane
4. **Request history** - `/my_requests` to see user's past requests
5. **Attachments** - Allow users to attach screenshots/files
6. **Labels/Tags** - Auto-tag requests based on keywords
7. **SLA tracking** - Track response time, escalate if no admin response
8. **Multi-language** - Support English/Russian language selection

### Alternative Module

The `support_requests` module (`app/modules/support_requests/`) offers a more sophisticated flow:
- Inline buttons instead of ForceReply
- Step-by-step: title → description → priority
- Better UX for complex requests

To switch:
1. Comment out `chat_support_router` in main.py:273
2. Uncomment `support_requests_router` import/registration
3. Restart bot

---

## 📚 Related Documentation

- [CLAUDE.md](../../CLAUDE.md) - Main development guide
- [Task Reports Guide](./task-reports-guide.md) - Similar FSM-based module
- [Plane API Integration](../../app/integrations/plane/README.md) - Plane API details

---

**Last Updated:** 2025-10-22
**Module Version:** 1.0 PRODUCTION READY
**Questions?** Check logs: `make bot-logs | grep support`
