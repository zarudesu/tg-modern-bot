"""Morning digest — AI-summarized daily overview for ADHD users.

Sends at 09:00 MSK via the bot's scheduler.
"""

import asyncio
from datetime import datetime, time

import pytz

from ...core.ai.ai_manager import ai_manager
from ...integrations.plane import plane_api
from ...utils.logger import bot_logger
from ...config import settings
from . import plane_service
from .handlers import _get_plane_email, _ai_chat

DIGEST_TIME = time(9, 0)  # 09:00
DIGEST_TZ = pytz.timezone("Europe/Moscow")

DIGEST_PROMPT = """Создай КРАТКИЙ утренний дайджест для IT-специалиста с СДВГ.

ФОРМАТ (строго):
1. Одна строка-мотивация (поддержка, не давление)
2. TOP-3 задачи на сегодня с объяснением ПОЧЕМУ
3. Если есть горящие просроченные — предупреди (кратко)
4. Итог одной строкой

Используй HTML: <b>жирный</b>, <i>курсив</i>.
Максимум 10 строк. Никаких списков всех задач.

ДАННЫЕ:
{plane_data}
"""


async def build_digest(user_id: int) -> str | None:
    """Build AI-powered morning digest for a user."""
    email = _get_plane_email(user_id)

    try:
        tasks_text = await plane_service.get_my_tasks_summary(email)
        overdue_text = await plane_service.get_overdue_summary(email)
        plane_data = f"{tasks_text}\n\n{overdue_text}"
    except Exception as e:
        bot_logger.error(f"Digest data error for {user_id}: {e}")
        return None

    if "нет открытых задач" in tasks_text.lower():
        return None

    prompt = DIGEST_PROMPT.format(plane_data=plane_data[:4000])

    try:
        return await _ai_chat("Утренний дайджест задач", prompt)
    except Exception as e:
        bot_logger.error(f"Digest AI error for {user_id}: {e}")
        return None


async def send_digest(bot, user_id: int):
    """Send morning digest to a user."""
    text = await build_digest(user_id)
    if not text:
        return

    try:
        await bot.send_message(
            chat_id=user_id,
            text=f"<b>Доброе утро!</b>\n\n{text}",
            parse_mode="HTML",
        )
        bot_logger.info(f"Morning digest sent to {user_id}")
    except Exception as e:
        bot_logger.error(f"Failed to send digest to {user_id}: {e}")


async def digest_loop(bot):
    """Background loop — check every 60s if it's digest time."""
    sent_today = set()

    while True:
        try:
            now = datetime.now(DIGEST_TZ)

            if now.hour == DIGEST_TIME.hour and now.minute == DIGEST_TIME.minute:
                today = now.date()
                for admin_id in settings.admin_user_id_list:
                    key = (admin_id, today)
                    if key not in sent_today:
                        sent_today.add(key)
                        asyncio.create_task(send_digest(bot, admin_id))

                # Cleanup old dates
                sent_today = {k for k in sent_today if k[1] == today}

        except Exception as e:
            bot_logger.error(f"Digest loop error: {e}")

        await asyncio.sleep(60)
