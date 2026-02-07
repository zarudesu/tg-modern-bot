"""Per-user conversation memory in Redis for /plane assistant."""

import time
from typing import List, Optional

from ...services.redis_service import redis_service
from ...utils.logger import bot_logger

CONTEXT_TTL = 1800  # 30 minutes
CONTEXT_KEY = "plane_chat"
MAX_MESSAGES = 20


async def get_context(user_id: int) -> List[dict]:
    key = f"{CONTEXT_KEY}:{user_id}"
    data = await redis_service.get_json(key)
    return data.get("messages", []) if data else []


async def add_message(user_id: int, role: str, content: str):
    key = f"{CONTEXT_KEY}:{user_id}"
    data = await redis_service.get_json(key) or {"messages": []}
    data["messages"].append({"role": role, "content": content, "ts": time.time()})
    data["messages"] = data["messages"][-MAX_MESSAGES:]
    await redis_service.set_json(key, data, ttl=CONTEXT_TTL)


async def get_last_context_summary(user_id: int) -> str:
    """Build a short conversation summary for the AI system prompt."""
    messages = await get_context(user_id)
    if not messages:
        return ""
    lines = []
    for m in messages[-6:]:
        role_label = "User" if m["role"] == "user" else "Bot"
        text = m["content"][:200]
        lines.append(f"{role_label}: {text}")
    return "\n".join(lines)


async def clear_context(user_id: int):
    await redis_service.delete(f"{CONTEXT_KEY}:{user_id}")
