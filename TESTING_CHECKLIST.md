# Testing Guide

## Automated Tests (pytest)

95 тестов: 75 unit + 20 integration. Запускаются локально перед деплоем.

### Quick Start

```bash
# Установить dev-зависимости (первый раз)
pip install -r requirements-dev.txt

# Запуск
make test              # Unit tests (быстро, ~1.5s)
make test-all          # Все + coverage
make test-integration  # Integration tests
make test-coverage     # HTML coverage report → htmlcov/index.html
```

### Что тестируется

#### Unit Tests (`tests/unit/`)

| Файл | Тесты | Что проверяет |
|------|-------|---------------|
| `test_plane_models.py` | 20+ | PlaneTask: is_overdue, priority_emoji, state_emoji, task_url |
| `test_duration_parser.py` | 20+ | parse_duration_to_minutes: "1 час"→60, "2ч 30м"→150 |
| `test_settings.py` | 15+ | Settings: admin_user_id_list, is_admin, telegram token |
| `test_ai_helpers.py` | 15+ | _edit_distance_ratio: identical→0.0, different→1.0 |

#### Integration Tests (`tests/integration/`)

| Файл | Тесты | Что проверяет |
|------|-------|---------------|
| `test_plane_api.py` | 10+ | PlaneAPIClient: GET/POST, auth errors, rate limit retry (aioresponses mock) |
| `test_webhook_server.py` | 10+ | WebhookServer: health, AI task result, Plane webhook (aiohttp TestClient) |

### Инфраструктура

- `pyproject.toml` — конфигурация pytest, coverage, markers
- `tests/conftest.py` — fixtures (mock_bot, plane_task_factory), env overrides, SQLite mock DB
- `requirements-dev.txt` — pytest, pytest-asyncio, pytest-cov, aioresponses, aiosqlite

### Написание новых тестов

```python
# tests/unit/test_example.py
import pytest
from app.integrations.plane.models import PlaneTask

def test_something(plane_task_factory):
    """plane_task_factory — fixture из conftest.py."""
    task = plane_task_factory(name="Test", priority="high")
    assert task.priority_emoji == "🟠"

@pytest.mark.parametrize("input,expected", [
    ("1 час", 60),
    ("30 мин", 30),
])
def test_parsing(input, expected):
    from app.utils.duration_parser import parse_duration_to_minutes
    assert parse_duration_to_minutes(input) == expected
```

### Legacy тесты

32 старых ad-hoc скрипта перемещены в `tests/legacy/`. Не включены в pytest. Можно запускать вручную: `python3 tests/legacy/test_basic.py`.

---

## Production Diagnostics (в Telegram)

Админские команды для проверки боевого бота:

### `/diag` — System Diagnostics

Проверяет все подсистемы, timeout 10s на каждый check:

| Check | Что проверяет |
|-------|---------------|
| Database | `SELECT 1` + count users, latency |
| Redis | `ping()`, `dbsize()`, members cache |
| Plane API | `test_connection()`, project count |
| Webhook | `GET http://localhost:8080/health` |
| AI Provider | providers_count, default provider |
| Migrations | `alembic_version` table |

Пример ответа:
```
System Diagnostics

[OK] Database — 2ms | Users: 5
[OK] Redis — Connected | Keys: 47
[OK] Plane API — hhivp | Projects: 27
[OK] Webhook — 6 routes | ok
[OK] AI Provider — openrouter (default) | 1 provider(s)
[OK] Migrations — Current: 013

All systems operational (6/6)
```

### `/ai_quality [days]` — AI Detection Quality

Анализирует DetectedIssue записи за N дней (default: 30):

- **Precision**: accepted / (accepted + rejected)
- **Detection rate**: total / days
- **Feedback distribution**: accepted, rejected, corrected, no_feedback
- **Confidence buckets**: accept rate по уровням уверенности
- **Correction distance**: среднее расстояние редактирования
- **Per-model stats**: precision по моделям AI

### `/plane_audit` — Deep Plane Audit

- Overdue tasks, stale (>7d, >14d), unassigned
- Workload distribution, recently completed
- AI recommendations

### `/plane_status` — AI Status Report

- AI-powered analysis open issues by state
- Highlights stale tasks (>7 days without update)

---

## Deploy Integration

```bash
# deploy.sh автоматически запускает тесты перед деплоем
./deploy.sh full     # test → push → pull → build → rebuild → logs
./deploy.sh test     # только pytest (exit 1 при ошибках)
./deploy.sh diag     # remote health check (curl + container status)

# Makefile
make test            # pytest tests/unit/
make test-all        # pytest all + coverage
```

---

## Troubleshooting

### Тесты не проходят

```bash
# Подробный вывод ошибок
python3 -m pytest tests/unit/ -v --tb=long

# Запуск одного теста
python3 -m pytest tests/unit/test_plane_models.py::test_is_overdue_past_date -v
```

### conftest.py ошибки

- `ValidationError: Extra inputs are not permitted` → .env файл в CWD содержит лишние переменные. conftest.py делает `os.chdir(tmpdir)` чтобы обойти это.
- `TypeError: Invalid argument(s) 'pool_size'` → SQLite не поддерживает PG pool params. conftest.py инжектирует mock database module.

### Production бот не отвечает

```bash
ssh hhivp@rd.hhivp.com "docker logs hhivp-bot-app-prod --tail 50"
ssh hhivp@rd.hhivp.com "docker ps --filter name=hhivp-bot"
ssh hhivp@rd.hhivp.com "curl -s http://localhost:8083/health"
```
