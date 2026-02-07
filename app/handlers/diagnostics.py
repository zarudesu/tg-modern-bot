"""
System Diagnostics — /diag command.

Runs read-only health checks against all subsystems and reports results.
"""

import asyncio
import time
from datetime import datetime, timezone

from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from sqlalchemy import text, select

from ..config import settings
from ..utils.logger import bot_logger

router = Router(name="diagnostics")


async def _check_database() -> dict:
    """Check database connectivity and basic stats."""
    from ..database.database import AsyncSessionLocal
    from ..database.models import BotUser

    start = time.monotonic()
    async with AsyncSessionLocal() as session:
        await session.execute(text("SELECT 1"))
        latency_ms = int((time.monotonic() - start) * 1000)

        result = await session.execute(select(BotUser.id))
        user_count = len(result.all())

    return {"ok": True, "details": f"{latency_ms}ms | Users: {user_count}"}


async def _check_redis() -> dict:
    """Check Redis connectivity and stats."""
    from ..services.redis_service import redis_service

    if not redis_service.is_connected:
        return {"ok": False, "details": "Not connected (using fallback)"}

    await redis_service._redis.ping()
    db_size = await redis_service._redis.dbsize()

    # Check specific cache keys
    members_exists = await redis_service.exists("plane:members")
    members_status = "active" if members_exists else "empty"

    return {"ok": True, "details": f"Connected | Keys: {db_size} | Members cache: {members_status}"}


async def _check_plane() -> dict:
    """Check Plane API connectivity."""
    from ..integrations.plane import plane_api

    if not plane_api.configured:
        return {"ok": False, "details": "Not configured"}

    result = await plane_api.test_connection()
    if result.get("success"):
        projects = await plane_api.get_projects()
        project_count = len(projects) if projects else 0
        return {
            "ok": True,
            "details": f"{settings.plane_workspace_slug} | Projects: {project_count}",
        }
    else:
        return {"ok": False, "details": result.get("error", "Connection failed")}


async def _check_webhook() -> dict:
    """Check internal webhook server."""
    import aiohttp

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "http://localhost:8080/health",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {"ok": True, "details": f"6 routes | {data.get('status', 'ok')}"}
                else:
                    return {"ok": False, "details": f"HTTP {resp.status}"}
    except Exception as e:
        return {"ok": False, "details": str(e)[:50]}


async def _check_ai() -> dict:
    """Check AI provider availability."""
    from ..core.ai.ai_manager import ai_manager

    count = ai_manager.providers_count
    if count == 0:
        return {"ok": False, "details": "No providers configured"}

    providers = ai_manager.list_providers()
    default_name = "none"
    for p in providers:
        if p.get("is_default"):
            default_name = p.get("name", "unknown")
            break

    return {"ok": True, "details": f"{default_name} (default) | {count} provider(s)"}


async def _check_migrations() -> dict:
    """Check alembic migration status."""
    from ..database.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(text("SELECT version_num FROM alembic_version"))
            row = result.first()
            current = row[0] if row else "none"
        except Exception:
            current = "table missing"

    return {"ok": True, "details": f"Current: {current}"}


@router.message(Command("diag"))
async def cmd_diag(message: Message):
    """
    /diag — Run system diagnostics (admin-only).
    Checks: Database, Redis, Plane API, Webhook, AI, Migrations.
    """
    if not settings.is_admin(message.from_user.id):
        await message.answer("Admin only")
        return

    status_msg = await message.answer("Running diagnostics...")

    checks = [
        ("Database", _check_database),
        ("Redis", _check_redis),
        ("Plane API", _check_plane),
        ("Webhook", _check_webhook),
        ("AI Provider", _check_ai),
        ("Migrations", _check_migrations),
    ]

    results = []
    ok_count = 0

    for name, check_fn in checks:
        try:
            result = await asyncio.wait_for(check_fn(), timeout=10)
            results.append((name, result))
            if result.get("ok"):
                ok_count += 1
        except asyncio.TimeoutError:
            results.append((name, {"ok": False, "details": "Timeout (10s)"}))
        except Exception as e:
            results.append((name, {"ok": False, "details": str(e)[:80]}))

    # Format report
    lines = ["<b>System Diagnostics</b>\n"]
    for name, result in results:
        icon = "[OK]" if result.get("ok") else "[FAIL]"
        details = result.get("details", "")
        lines.append(f"<code>{icon}</code> <b>{name}</b> — {details}")

    total = len(checks)
    if ok_count == total:
        lines.append(f"\nAll systems operational ({ok_count}/{total})")
    else:
        lines.append(f"\n{ok_count}/{total} OK, {total - ok_count} issues")

    try:
        await status_msg.edit_text("\n".join(lines), parse_mode="HTML")
    except Exception as e:
        bot_logger.error(f"Error sending diag report: {e}")
        await status_msg.edit_text(f"Diagnostics error: {e}")
