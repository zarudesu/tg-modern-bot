"""
Обработчики команд для тестирования Plane интеграции
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.database import get_async_session
from ..integrations.plane_with_mentions import PlaneNotificationService, PlaneWebhookPayload, PlaneIssue
from ..utils.logger import bot_logger, log_user_action
from ..config import settings

router = Router()


@router.message(Command("test_plane"))
async def test_plane_notification(message: Message):
    """Тестирование уведомлений Plane"""
    try:
        user_id = message.from_user.id
        log_user_action(user_id, "test_plane")
        
        # Создаем тестовые данные
        test_issue = PlaneIssue(
            id="HARZL-19",
            name="Принтер на складе добавить в принтсервер прикрутить политику",
            description="Настройка принтера для работы с принт-сервером и применение политик печати",
            state="todo",
            priority="none",
            assignee="Dmitriy Gusev",  # Это должно превратиться в @strikerstr
            project="HarzLabs",
            created_by="Konstantin Makeykin",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        test_payload = PlaneWebhookPayload(
            event="created",
            action="created",
            issue=test_issue,
            actor={"display_name": "Konstantin Makeykin", "email": "konstantin@example.com"}
        )
        
        async for session in get_async_session():
            # Создаем сервис и отправляем тестовое уведомление
            plane_service = PlaneNotificationService(message.bot, session)
            
            # Устанавливаем chat_id на текущий чат для тестирования
            plane_service.chat_id = message.chat.id
            plane_service.topic_id = None
            
            success = await plane_service.process_webhook(test_payload)
            
            if success:
                await message.answer(
                    "✅ Тестовое уведомление Plane отправлено!\n\n"
                    "Должно появиться сообщение с упоминанием @strikerstr вместо 'Dmitriy Gusev'"
                )
            else:
                await message.answer("❌ Ошибка при отправке тестового уведомления")
                
    except Exception as e:
        bot_logger.error(f"Error in test_plane_notification: {e}")
        await message.answer(f"❌ Ошибка тестирования: {str(e)}")


@router.message(Command("test_plane_update"))
async def test_plane_update_notification(message: Message):
    """Тестирование уведомления об обновлении задачи Plane"""
    try:
        user_id = message.from_user.id
        log_user_action(user_id, "test_plane_update")
        
        # Создаем тестовые данные для обновления
        test_issue = PlaneIssue(
            id="HARZL-19",
            name="Принтер на складе добавить в принтсервер прикрутить политику",
            description="Настройка принтера для работы с принт-сервером и применение политик печати",
            state="in_progress",  # Изменили статус
            priority="high",      # Изменили приоритет
            assignee="Тимофей Батырев",  # Переназначили на Тимофея
            project="HarzLabs",
            created_by="Konstantin Makeykin",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        test_changes = {
            "state": {
                "old": "todo",
                "new": "in_progress"
            },
            "priority": {
                "old": "none",
                "new": "high"
            },
            "assignee": {
                "old": "Dmitriy Gusev",
                "new": "Тимофей Батырев"
            }
        }
        
        test_payload = PlaneWebhookPayload(
            event="updated",
            action="updated",
            issue=test_issue,
            changes=test_changes,
            actor={"display_name": "Konstantin Makeykin", "email": "konstantin@example.com"}
        )
        
        async for session in get_async_session():
            plane_service = PlaneNotificationService(message.bot, session)
            plane_service.chat_id = message.chat.id
            plane_service.topic_id = None
            
            success = await plane_service.process_webhook(test_payload)
            
            if success:
                await message.answer(
                    "✅ Тестовое уведомление об обновлении Plane отправлено!\n\n"
                    "Должно показать:\n"
                    "• Изменение статуса: todo → in_progress\n"
                    "• Изменение приоритета: none → high\n"
                    "• Переназначение: @strikerstr → @spiritphoto"
                )
            else:
                await message.answer("❌ Ошибка при отправке тестового уведомления")
                
    except Exception as e:
        bot_logger.error(f"Error in test_plane_update_notification: {e}")
        await message.answer(f"❌ Ошибка тестирования: {str(e)}")


@router.message(Command("plane_workers"))
async def show_plane_workers_mapping(message: Message):
    """Показать маппинг пользователей Plane на исполнителей"""
    try:
        user_id = message.from_user.id
        log_user_action(user_id, "plane_workers")
        
        async for session in get_async_session():
            from ..database.work_journal_models import WorkJournalWorker
            from sqlalchemy import select
            
            # Получаем всех исполнителей
            result = await session.execute(
                select(WorkJournalWorker)
                .where(WorkJournalWorker.is_active == True)
                .order_by(WorkJournalWorker.display_order, WorkJournalWorker.name)
            )
            workers = result.scalars().all()
            
            if not workers:
                await message.answer("❌ Исполнители не найдены")
                return
            
            text = "👥 **Маппинг исполнителей Plane:**\n\n"
            
            for worker in workers:
                text += f"**{worker.name}**\n"
                text += f"├ Telegram: {worker.telegram_username or 'не указан'}\n"
                text += f"├ User ID: {worker.telegram_user_id or 'не указан'}\n"
                text += f"├ Упоминания: {'✅' if worker.mention_enabled else '❌'}\n"
                
                if worker.plane_user_names:
                    try:
                        import json
                        plane_names = json.loads(worker.plane_user_names)
                        text += f"└ Plane имена: {', '.join(plane_names)}\n"
                    except (json.JSONDecodeError, TypeError):
                        text += f"└ Plane имена: ошибка формата\n"
                else:
                    text += f"└ Plane имена: не настроены\n"
                    
                text += "\n"
            
            await message.answer(text, parse_mode="Markdown")
                
    except Exception as e:
        bot_logger.error(f"Error in show_plane_workers_mapping: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")


@router.message(Command("test_plane_n8n"))
async def test_plane_n8n_notification(message: Message):
    """Тестирование уведомлений Plane от n8n"""
    try:
        user_id = message.from_user.id
        log_user_action(user_id, "test_plane_n8n")
        
        # Создаем тестовые данные как они приходят от n8n
        test_data = {
            "source": "plane_n8n",
            "event_type": "plane_issue_created",
            "data": {
                "issue": {
                    "id": "HARZL-19",
                    "name": "Принтер на складе добавить в принтсервер прикрутить политику",
                    "description": "Настройка принтера для работы с принт-сервером и применение политик печати",
                    "state": "todo",
                    "priority": "none",
                    "assignee": "Dmitriy Gusev",  # Это должно превратиться в @strikerstr
                    "project": "HarzLabs",
                    "created_at": "2025-07-31T23:38:00Z"
                },
                "actor": {
                    "display_name": "Konstantin Makeykin"
                }
            }
        }
        
        async for session in get_async_session():
            from ..services.plane_n8n_handler import PlaneN8nHandler, PlaneWebhookData
            
            # Создаем payload
            payload = PlaneWebhookData(**test_data)
            
            # Создаем обработчик и отправляем тестовое уведомление
            plane_handler = PlaneN8nHandler(message.bot, session)
            
            # Устанавливаем chat_id на текущий чат для тестирования
            plane_handler.chat_id = message.chat.id
            plane_handler.topic_id = None
            
            success = await plane_handler.process_plane_webhook(payload)
            
            if success:
                await message.answer(
                    "✅ Тестовое уведомление Plane от n8n отправлено!\n\n"
                    "Должно появиться сообщение в формате:\n"
                    "╭─ 🎯 HARZL-19\n"
                    "├ 📝 Принтер на складе...\n"
                    "├ 👥 @strikerstr  ← вместо 'Dmitriy Gusev'\n"
                    "╰─ 🔗 Открыть в Plane"
                )
            else:
                await message.answer("❌ Ошибка при отправке тестового уведомления")
                
    except Exception as e:
        bot_logger.error(f"Error in test_plane_n8n_notification: {e}")
        await message.answer(f"❌ Ошибка тестирования: {str(e)}")


@router.message(Command("plane_config"))
async def show_plane_config(message: Message):
    """Показать конфигурацию Plane интеграции"""
    try:
        user_id = message.from_user.id
        log_user_action(user_id, "plane_config")
        
        config_text = "⚙️ **Конфигурация Plane интеграции:**\n\n"
        
        # Проверяем настройки
        plane_chat_id = getattr(settings, 'plane_chat_id', None)
        plane_topic_id = getattr(settings, 'plane_topic_id', None)
        webhook_secret = getattr(settings, 'plane_webhook_secret', None)
        
        config_text += f"**Chat ID:** {plane_chat_id or 'не настроен'}\n"
        config_text += f"**Topic ID:** {plane_topic_id or 'не настроен'}\n"
        config_text += f"**Webhook Secret:** {'✅ настроен' if webhook_secret else '❌ не настроен'}\n"
        config_text += f"**Текущий чат ID:** {message.chat.id}\n\n"
        
        config_text += "**Команды тестирования:**\n"
        config_text += "• `/test_plane` - тест прямого webhook Plane\n"
        config_text += "• `/test_plane_n8n` - тест webhook от n8n\n"
        config_text += "• `/test_plane_update` - тест обновления задачи\n"
        config_text += "• `/plane_workers` - маппинг исполнителей\n"
        config_text += "• `/plane_config` - эта информация\n"
        
        await message.answer(config_text, parse_mode="Markdown")
        
    except Exception as e:
        bot_logger.error(f"Error in show_plane_config: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")
