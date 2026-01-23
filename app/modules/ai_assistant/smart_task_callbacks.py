"""
Smart Task Detection - callback handlers

Обработчики для кнопок предложений по созданию задач.
"""

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery

from .task_suggestion_handler import get_detected_task
from ...database.database import get_async_session
from ...integrations.plane import plane_api
from ...config import settings
from ...utils.logger import bot_logger


router = Router(name="smart_task_callbacks")


@router.callback_query(F.data.startswith("smart_task:create:"))
async def callback_create_smart_task(callback: CallbackQuery, bot: Bot):
    """
    Create task in Plane from detected task suggestion.

    callback_data format: smart_task:create:{chat_id}:{message_id}
    """
    try:
        parts = callback.data.split(":")
        if len(parts) < 4:
            await callback.answer("Ошибка: неверный формат данных", show_alert=True)
            return

        chat_id = int(parts[2])
        message_id = int(parts[3])

        # Get stored task data
        task_data = get_detected_task(chat_id, message_id)

        if not task_data:
            await callback.answer(
                "Данные задачи устарели. Используйте /task для создания.",
                show_alert=True
            )
            # Delete the suggestion message
            try:
                await callback.message.delete()
            except:
                pass
            return

        detected_task = task_data.get("detected_task", "")
        original_text = task_data.get("original_text", "")
        suggested_assignee = task_data.get("suggested_assignee")
        confidence = task_data.get("confidence", 0)

        # Show processing status
        await callback.answer("Создаю задачу в Plane...")
        await callback.message.edit_text(
            "🔄 <b>Создание задачи в Plane...</b>",
            parse_mode="HTML"
        )

        # Get default project for this chat
        # For now, use a default project; can be extended to use chat mappings
        async for session in get_async_session():
            # Try to find chat mapping for project
            from ...database.support_requests_models import ChatProjectMapping
            from sqlalchemy import select

            result = await session.execute(
                select(ChatProjectMapping)
                .where(ChatProjectMapping.chat_id == chat_id)
                .where(ChatProjectMapping.is_active == True)
            )
            chat_mapping = result.scalar_one_or_none()

            project_id = None
            if chat_mapping:
                project_id = chat_mapping.plane_project_id

        # Create task title (first 50 chars of detected task)
        task_title = detected_task[:50]
        if len(detected_task) > 50:
            task_title += "..."

        # Create task description
        task_description = f"""**Автоматически обнаруженная задача**

{detected_task}

---
**Исходное сообщение:**
{original_text[:500]}

---
🤖 Обнаружено AI (уверенность: {confidence:.0%})
📍 Чат: {chat_id}
"""

        # Create task in Plane
        try:
            # Use default workspace project if no mapping found
            if not project_id:
                # Get first available project
                projects = await plane_api.get_projects()
                if projects:
                    project_id = projects[0].get("id")

            if not project_id:
                await callback.message.edit_text(
                    "❌ <b>Ошибка:</b> Не найден проект для создания задачи.\n\n"
                    "Настройте маппинг чата через /setup_chat",
                    parse_mode="HTML"
                )
                return

            # Create issue
            issue_data = {
                "name": task_title,
                "description_html": f"<p>{task_description.replace(chr(10), '<br/>')}</p>",
                "priority": "medium",
            }

            # Add assignee if detected and can be mapped
            if suggested_assignee:
                # Try to find user in Plane
                # This would require mapping; skip for now
                pass

            created_issue = await plane_api.create_issue(
                project_id=project_id,
                issue_data=issue_data
            )

            if created_issue:
                issue_id = created_issue.get("sequence_id", "?")

                # Success message
                success_text = (
                    f"✅ <b>Задача создана!</b>\n\n"
                    f"📋 <b>#{issue_id}:</b> {task_title}\n"
                )

                if suggested_assignee:
                    success_text += f"👤 Предложенный исполнитель: {suggested_assignee}\n"

                success_text += f"\n<i>Задача добавлена в Plane</i>"

                await callback.message.edit_text(
                    success_text,
                    parse_mode="HTML"
                )

                bot_logger.info(
                    f"Smart task created: #{issue_id} in project {project_id}"
                )
            else:
                await callback.message.edit_text(
                    "❌ <b>Ошибка:</b> Не удалось создать задачу в Plane",
                    parse_mode="HTML"
                )

        except Exception as e:
            bot_logger.error(f"Failed to create smart task: {e}")
            await callback.message.edit_text(
                f"❌ <b>Ошибка:</b> {str(e)}",
                parse_mode="HTML"
            )

    except Exception as e:
        bot_logger.error(f"Error in smart_task:create callback: {e}")
        await callback.answer("Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("smart_task:ignore:"))
async def callback_ignore_smart_task(callback: CallbackQuery):
    """
    Ignore task suggestion - just delete the message.

    callback_data format: smart_task:ignore:{chat_id}:{message_id}
    """
    try:
        await callback.answer("Предложение скрыто")

        # Delete the suggestion message
        try:
            await callback.message.delete()
        except:
            # If can't delete, just edit
            await callback.message.edit_text(
                "🚫 <i>Предложение проигнорировано</i>",
                parse_mode="HTML"
            )

    except Exception as e:
        bot_logger.error(f"Error in smart_task:ignore callback: {e}")
        await callback.answer("Ошибка", show_alert=True)
