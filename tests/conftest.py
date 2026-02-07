"""
Shared pytest fixtures for tg-modern-bot test suite.

IMPORTANT: Environment overrides MUST happen before any app imports,
because app/config.py creates a global Settings() at import time (line 151).
The .env file may contain vars not in Settings → must prevent .env loading.
"""

import os
import sys

# Prevent pydantic-settings from reading .env file by changing to a temp dir
# that has no .env file. We set all needed vars via os.environ.
_original_cwd = os.getcwd()
_test_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_test_dir)

# Override env vars BEFORE any app imports
os.environ["TELEGRAM_TOKEN"] = "0000000000:AAHtest_token_for_pytest_AAAAAAAAA"
os.environ["TELEGRAM_API_ID"] = "123456"
os.environ["TELEGRAM_API_HASH"] = "test_api_hash_for_pytest"
os.environ["ADMIN_USER_IDS"] = "28795547,999999"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/15"
os.environ["PLANE_API_URL"] = "https://plane.test.local"
os.environ["PLANE_API_TOKEN"] = "test_plane_token_for_pytest"
os.environ["PLANE_WORKSPACE_SLUG"] = "test-workspace"
os.environ["DAILY_TASKS_ENABLED"] = "false"
os.environ["ENVIRONMENT"] = "test"
os.environ["LOG_LEVEL"] = "WARNING"

# Temporarily change to a directory without .env to prevent pydantic from loading it
import tempfile
_tmpdir = tempfile.mkdtemp()
os.chdir(_tmpdir)

# Ensure project root is on sys.path for app imports
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Pre-create a SQLite-compatible async engine BEFORE any app.database imports.
# app/database/database.py uses pool_size/max_overflow which are PG-only.
_test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    echo=False,
)
_test_session_factory = async_sessionmaker(
    _test_engine, class_=AsyncSession, expire_on_commit=False
)

# Create mock database module that the rest of the app will use
import types
_mock_db_module = types.ModuleType("app.database.database")
_mock_db_module.engine = _test_engine
_mock_db_module.AsyncSessionLocal = _test_session_factory
_mock_db_module.get_async_session = AsyncMock()
_mock_db_module.init_db = AsyncMock()
_mock_db_module.close_db = AsyncMock()
sys.modules["app.database.database"] = _mock_db_module

# Import triggers app/config.py Settings() creation, but without .env file
from app.integrations.plane.models import PlaneTask, PlaneProject, PlaneUser, PlaneState

# Restore original cwd after imports
os.chdir(_original_cwd)


@pytest.fixture
def mock_bot():
    """Mock aiogram Bot instance."""
    bot = AsyncMock()
    bot.id = 0000000000
    bot.username = "test_bot"
    return bot


@pytest.fixture
def plane_task_factory():
    """Factory for creating PlaneTask instances with realistic defaults."""

    def _make(
        name="Test task",
        priority="medium",
        state="state-uuid-1",
        state_name="In Progress",
        target_date=None,
        assignees=None,
        assignee_name="Unassigned",
        project="proj-uuid-1",
        project_name="HHIVP",
        sequence_id=42,
        state_detail=None,
        **kwargs,
    ):
        return PlaneTask(
            id="issue-uuid-1",
            name=name,
            priority=priority,
            state=state,
            state_name=state_name,
            target_date=target_date,
            assignees=assignees or [],
            assignee_name=assignee_name,
            project=project,
            project_name=project_name,
            sequence_id=sequence_id,
            state_detail=state_detail,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
            **kwargs,
        )

    return _make


@pytest.fixture
def sample_plane_project():
    """Sample PlaneProject for tests."""
    return PlaneProject(
        id="proj-uuid-1",
        name="HHIVP",
        identifier="HHIVP",
        workspace="workspace-uuid",
    )


@pytest.fixture
def sample_plane_members():
    """Sample workspace members list (as returned by _get_cached_members)."""
    return [
        {"id": "user-uuid-1", "display_name": "Zardes", "email": "zardes@hhivp.com"},
        {"id": "user-uuid-2", "display_name": "Striker", "email": "striker@hhivp.com"},
        {"id": "user-uuid-3", "display_name": "Admin", "email": "admin@hhivp.com"},
    ]
