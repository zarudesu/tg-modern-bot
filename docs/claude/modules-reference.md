# Modules Reference (detailed)

> This file contains detailed module documentation extracted from CLAUDE.md.
> For quick overview, see module status table in CLAUDE.md.

## Task Reports Module (PRODUCTION READY)

**Purpose:** Automated client reporting when support tasks completed in Plane.so

**Quick Flow:**
```
Plane task "Done" → n8n webhook → Bot notification → Admin fills report →
Client receives + Google Sheets + Group notification
```

**Key Features:**
- Auto-fills task data from Plane (title, description, assignees)
- Independent field editing (duration, travel, company, workers)
- Company mapping (15+ companies: Plane project → Russian names)
- Workers autofill from Plane assignees
- Complete integration: client chat + work_journal + Google Sheets + group notification
- **Voice Fill** - заполнение отчёта голосом с детекцией конфликтов

**Voice Fill:**

Вместо ручного ввода можно отправить голосовое:
```
«2 часа, выезд, Дима и Костя, настроили принтер и обновили ПО»
```

**Как работает:**
1. Admin нажимает "Заполнить отчёт"
2. Отправляет голосовое (или текст)
3. AI извлекает: длительность, тип работы, исполнителей, описание
4. Если данные расходятся с Plane — показывает UI для выбора
5. Применяет данные и показывает превью

**Детекция конфликтов:**
- Сравнивает компанию из голоса vs Plane project
- Сравнивает исполнителей из голоса vs Plane assignees
- Если отличаются — кнопки выбора "Голос" или "Plane"

**Файлы:**
- `app/modules/task_reports/handlers/voice_fill.py` - Voice fill handler
- `app/modules/task_reports/handlers/creation.py` - Shows voice hint

**Full Documentation:** [`docs/guides/task-reports-guide.md`](../guides/task-reports-guide.md)

---

## Support Requests Module (PRODUCTION READY)

**Purpose:** Allow users to create support requests from group chats → auto-creates tasks in Plane.so

**Flow 1: User Creates Request**
```
User runs /request in group → Types problem description →
Bot creates Plane task + notifies admins → User gets ticket number
```

**Flow 2: Create Task from Any Message**
```
User sees problem in group message → Anyone replies with /task →
Bot creates Plane task with original author as owner + full context
```

**Key Features:**
- Simple user flow: `/request` → type problem → done
- `/task` command - create tasks from any message via reply
- Auto-creates tasks in Plane with full user context
- Maps group chats to specific Plane projects
- FSM-based state management (no message conflicts)
- 10-minute timeout for `/request` flow

**User Commands:**
- `/request` - Create new support request (FSM flow)
- `/task [comment]` - Reply to any message to create task (instant)

**Admin Commands:**
- `/setup_chat` - Configure group for support requests
- `/list_chats` - List all configured groups
- `/remove_chat` - Remove group configuration

**`/task` Command Details:**
- **Usage:** Reply to any message + `/task [optional comment]`
- **Available to:** All users (not just admins)
- **Priority:** Always medium
- **Task title:** Auto-generated from first 50 characters
- **Task owner:** Original message author
- **Context saved in Plane comment:** Original author info, creator info, message link, comment, chat name, timestamp

**Full Documentation:** [`docs/guides/support-requests-guide.md`](../guides/support-requests-guide.md)

---

## Chat AI Analysis Module (PRODUCTION READY)

**Purpose:** AI-powered analysis of group chat messages for problem detection, summarization, and context tracking.

**Architecture:**
```
Messages → ChatContextService (DB) → ProblemDetector → Alert to Group
                                  → SummaryService → /ai_summary command
```

**Key Components:**

| Component | File | Purpose |
|-----------|------|---------|
| `ChatContextService` | `app/services/chat_context_service.py` | Persistent message storage in PostgreSQL |
| `ProblemDetectorService` | `app/services/problem_detector_service.py` | Keyword + AI problem detection |
| `SummaryService` | `app/services/summary_service.py` | AI-powered chat summarization |
| `ChatMessage` | `app/database/chat_ai_models.py` | SQLAlchemy model for messages |
| `ChatAISettings` | `app/database/chat_ai_models.py` | Per-chat AI configuration |
| `DetectedIssue` | `app/database/chat_ai_models.py` | Tracked problems/issues |

**Database Tables (Migration 009):**
- `chat_messages` - Persistent message history with AI analysis fields
- `chat_ai_settings` - Per-chat configuration (context size, feature toggles)
- `detected_issues` - Tracked problems with status workflow

**AI Commands (Admin only):**
```
/ai_summary [N]     - Generate summary of last N messages (default: 100)
/ai_daily           - Generate daily summary
/ai_problems        - Show open detected problems
/ai_settings        - View/change AI settings for chat
/monitor_status     - Show monitoring statistics
```

**Problem Detection:**
- Keyword matching - Russian problem keywords
- Question patterns - Detects unanswered questions
- Urgency boosters - "срочно", "!!!", CAPS detection
- AI semantic analysis - Uses OpenRouter for context-aware detection
- Rate limiting - 60 seconds cooldown per chat

---

## Voice Transcription Module (PRODUCTION READY)

**Purpose:** Voice-to-text transcription with AI extraction of work report data using FREE APIs

**Quick Flow:**
```
Admin sends voice message → HuggingFace Whisper (FREE) → Transcription →
OpenRouter AI (FREE) → Extract structured data → Match to DB →
Create Work Journal entries
```

**How It Works:**

1. **Voice → Text (HuggingFace Whisper)** - `openai/whisper-large-v3`, FREE
2. **Text → Structured Data (OpenRouter AI)** - `mistralai/devstral-2512:free`
3. **Multi-Entry Support** - Single voice message → multiple work entries

**Company Aliases (voice → official name):**

| Голосом | → В БД |
|---------|--------|
| "харизма", "хардслабс", "харц" | Харц Лабз |
| "софтфабрик", "фабрик" | СофтФабрик |
| "3д ру", "тридиру", "дыра" | 3Д.РУ |
| "сад", "здоровье" | Сад Здоровья |
| "дельта телеком" | Дельта |
| "штифтер" | Стифтер |
| "сосновка" | Сосновый бор |
| "вёшки", "вешки" | Вёшки 95 |
| "вондига" | Вондига Парк |
| "цифра" | ЦифраЦифра |
| "хивп", "эйчхивп" | HHIVP |

**Unmatched Names:** AI returns name + `company_unmatched: true` flag, UI shows warning.

**File:** `app/handlers/voice_transcription.py`

**Key Functions:**
- `transcribe_audio()` - HuggingFace Whisper transcription
- `extract_report_data_with_ai()` - OpenRouter AI extraction
- `get_valid_companies_and_workers()` - Fetch DB values for matching
- `handle_voice_message()` - Main handler for voice messages

---

## AI Task Detection v2 (PRODUCTION READY)

**Purpose:** Smart task creation from group messages with dedup, assignee selection, and training data.

**Flow:**
```
Message in group → Chat Monitor → AI detects task (confidence > 75%) →
Suggestion with "Create Task" button → Dedup check (similar issues) →
Task preview (title, priority, assignee, project) → Create in Plane
```

**Key Features:**
- Dedup detection — searches similar open issues before creating
- Assignee picker — inline buttons with workspace members (Redis cached)
- Task preview — edit before creation
- Reply in source chat — notify when task created
- Training data recording — feedback (accept/reject/correct) for AI improvement

**Handlers:**
- `app/handlers/ai_callbacks.py` — Callback flow: confirm → dedup → preview → assignee → create
- `app/modules/ai_assistant/task_suggestion_handler.py` — Event-driven suggestion sender

**Admin Commands:**
```
/plane_audit          Deep audit: overdue, stale, unassigned, workload
/plane_status         AI-powered status analysis by state
/ai_export [days]     Export training data (DetectedIssue records)
/ai_quality [days]    AI detection quality metrics (precision, confidence, per-model)
```

---

## System Diagnostics (PRODUCTION READY)

**Purpose:** Live health checks for all bot subsystems.

**Command:** `/diag` (admin-only)

**Checks:**
| Check | What | Source |
|-------|------|--------|
| Database | `SELECT 1`, user count | AsyncSessionLocal |
| Redis | `ping()`, `dbsize()`, cache | redis_service |
| Plane API | `test_connection()`, projects | plane_api |
| Webhook | `GET /health` | aiohttp internal |
| AI Provider | providers_count, default | ai_manager |
| Migrations | `alembic_version` table | SQL query |

Each check with `asyncio.wait_for(timeout=10)`.

**File:** `app/handlers/diagnostics.py`

---

## AI Quality Analytics (PRODUCTION READY)

**Purpose:** Analyze AI task detection quality from recorded feedback.

**Command:** `/ai_quality [days]` (admin-only, default: 30 days)

**Metrics:**
- **Precision**: accepted / (accepted + rejected)
- **Detection rate**: total / days
- **Feedback distribution**: accepted, rejected, corrected, no_feedback
- **Confidence buckets**: [0-0.3, 0.3-0.5, 0.5-0.7, 0.7-0.9, 0.9-1.0] — accept rate per bucket
- **Correction distance**: mean edit distance for corrected issues
- **Per-model stats**: precision by ai_model_used

**Data source:** `DetectedIssue` table (fields: user_feedback, confidence, correction_distance, ai_model_used)

**File:** `app/handlers/ai_quality.py`

---

## Enterprise Architecture (v3.0) - PRODUCTION

**Status:** Production ready, event bus used for AI task detection

**Event Bus** (`app/core/events/`): Reactive event-driven, priority-based, 7+ event types
**Plugin System** (`app/core/plugins/`): Dynamic plugin loading/unloading
**AI Abstractions** (`app/core/ai/`): Universal LLM provider interface (OpenRouter default)

**AI Assistant** (`app/modules/ai_assistant/`): `/ai`, `/ai_summary`, smart task detection
**Chat Monitor** (`app/modules/chat_monitor/`): All group messages, context (50 msgs/chat)
