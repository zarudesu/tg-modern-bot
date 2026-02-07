"""
Webhook сервер для получения уведомлений от внешних систем
"""
import json
import hmac
import hashlib
from datetime import datetime
from typing import Dict, Any
from aiohttp import web, ClientSession
from aiohttp.web import Request, Response
from aiogram import Bot

from ..utils.logger import bot_logger
# from ..integrations.plane_with_mentions import PlaneNotificationService, PlaneWebhookPayload
# from ..services.plane_n8n_handler import PlaneN8nHandler, PlaneWebhookData
from ..config import settings
from ..database.database import get_async_session


class WebhookServer:
    """HTTP сервер для обработки webhooks"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.app = web.Application()
        # plane_service будет создаваться в каждом запросе с новой сессией
        self.setup_routes()
    
    def setup_routes(self):
        """Настройка маршрутов"""
        # Legacy n8n webhook (will be deprecated)
        self.app.router.add_post('/webhooks/task-completed', self.handle_task_completed_webhook)
        # NEW: Direct Plane webhook (no n8n middleman)
        self.app.router.add_post('/webhooks/plane-direct', self.handle_plane_direct_webhook)

        # AI Integration webhooks (n8n → Bot)
        self.app.router.add_post('/webhooks/ai/task-result', self.handle_ai_task_result)
        self.app.router.add_post('/webhooks/ai/voice-result', self.handle_ai_voice_result)

        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/', self.root_handler)
    
    async def health_check(self, request: Request) -> Response:
        """Health check endpoint"""
        return web.json_response({
            'status': 'ok', 
            'service': 'telegram-bot-webhooks',
            'timestamp': str(datetime.utcnow())
        })
    
    async def root_handler(self, request: Request) -> Response:
        """Root endpoint"""
        return web.json_response({
            'service': 'Telegram Bot Webhooks',
            'endpoints': [
                '/webhooks/plane-direct - Direct Plane webhooks (RECOMMENDED)',
                '/webhooks/task-completed - Task completion reports (legacy, from n8n)',
                '/webhooks/ai/task-result - AI task detection results (from n8n)',
                '/webhooks/ai/voice-result - AI voice report results (from n8n)',
                '/health - Health check'
            ]
        })
    
    async def handle_plane_webhook(self, request: Request) -> Response:
        """Обработка webhook от Plane"""
        try:
            # Получаем данные
            data = await request.json()
            
            # Логируем получение webhook
            bot_logger.info(f"Received Plane webhook: {data.get('event', 'unknown')}")
            
            # Проверяем подпись если настроена
            webhook_secret = getattr(settings, 'plane_webhook_secret', None)
            if webhook_secret:
                signature = request.headers.get('X-Plane-Signature')
                if not self._verify_signature(json.dumps(data), signature, webhook_secret):
                    bot_logger.warning("Invalid Plane webhook signature")
                    return web.json_response({'error': 'Invalid signature'}, status=401)
            
            # Парсим payload
            try:
                payload = PlaneWebhookPayload(**data)
            except Exception as e:
                bot_logger.error(f"Invalid Plane webhook payload: {e}")
                return web.json_response({'error': 'Invalid payload format'}, status=400)
            
            # Создаем сессию БД и сервис для каждого запроса
            async for session in get_async_session():
                plane_service = PlaneNotificationService(self.bot, session)
                success = await plane_service.process_webhook(payload)
                
                if success:
                    return web.json_response({'status': 'processed'})
                else:
                    return web.json_response({'error': 'Processing failed'}, status=500)
            
        except json.JSONDecodeError:
            bot_logger.error("Invalid JSON in Plane webhook")
            return web.json_response({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            bot_logger.error(f"Error processing Plane webhook: {e}")
            return web.json_response({'error': 'Internal server error'}, status=500)
    
    async def handle_plane_n8n_webhook(self, request: Request) -> Response:
        """Обработка webhook от n8n с данными Plane"""
        try:
            # Получаем данные
            data = await request.json()
            
            # Логируем получение webhook
            bot_logger.info(f"Received Plane n8n webhook: {data.get('event_type', 'unknown')}")
            
            # Проверяем подпись если настроена
            webhook_secret = getattr(settings, 'plane_webhook_secret', None)
            if webhook_secret:
                signature = request.headers.get('X-N8n-Signature')
                if not self._verify_signature(json.dumps(data), signature, webhook_secret):
                    bot_logger.warning("Invalid n8n webhook signature")
                    return web.json_response({'error': 'Invalid signature'}, status=401)
            
            # Парсим payload
            try:
                payload = PlaneWebhookData(**data)
            except Exception as e:
                bot_logger.error(f"Invalid n8n Plane webhook payload: {e}")
                return web.json_response({'error': 'Invalid payload format'}, status=400)
            
            # Создаем сессию БД и обработчик для каждого запроса
            async for session in get_async_session():
                plane_handler = PlaneN8nHandler(self.bot, session)
                success = await plane_handler.process_plane_webhook(payload)
                
                if success:
                    return web.json_response({'status': 'processed'})
                else:
                    return web.json_response({'error': 'Processing failed'}, status=500)
            
        except json.JSONDecodeError:
            bot_logger.error("Invalid JSON in n8n Plane webhook")
            return web.json_response({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            bot_logger.error(f"Error processing n8n Plane webhook: {e}")
            return web.json_response({'error': 'Internal server error'}, status=500)
    
    async def handle_task_completed_webhook(self, request: Request) -> Response:
        """
        Обработка webhook от n8n когда задача Plane переведена в Done

        Ожидаемая структура данных от n8n:
        {
            "plane_issue_id": "uuid",
            "plane_sequence_id": 123,
            "plane_project_id": "uuid",
            "task_title": "Task name",
            "task_description": "Full description",
            "closed_by": {
                "display_name": "Zardes",
                "first_name": "Zardes",
                "email": "zarudesu@gmail.com"
            },
            "closed_at": "2025-10-07T12:00:00Z",
            "support_request_id": 5  # Optional
        }
        """
        try:
            # FIX (2026-01-21): Signature verification is OPTIONAL for backwards compatibility
            # n8n workflow may not send signature header
            webhook_secret = getattr(settings, 'n8n_webhook_secret', None) or getattr(settings, 'plane_webhook_secret', None)
            signature = request.headers.get('X-Webhook-Signature') or request.headers.get('X-N8n-Signature')

            if webhook_secret and signature:
                # Signature provided - verify it
                raw_body = await request.read()
                if not self._verify_signature(raw_body.decode(), signature, webhook_secret):
                    bot_logger.warning(
                        "Invalid webhook signature for task-completed",
                        extra={"remote_ip": request.remote}
                    )
                    return web.json_response({'error': 'Invalid signature'}, status=401)
                data = json.loads(raw_body)
                bot_logger.debug("✅ Webhook signature verified")
            elif webhook_secret and not signature:
                # Secret configured but no signature sent - allow with warning
                # This is for backwards compatibility with n8n workflows not yet configured
                bot_logger.warning(
                    "⚠️ Webhook received WITHOUT signature header. "
                    "Consider configuring HMAC signature in n8n workflow for security."
                )
                data = await request.json()
            else:
                # No secret configured - just process
                bot_logger.debug("Webhook signature verification not configured")
                data = await request.json()

            bot_logger.info(
                f"📨 Received task-completed webhook: "
                f"plane_issue={data.get('plane_issue_id')}, "
                f"seq_id={data.get('plane_sequence_id')}"
            )

            # Импортируем сервис
            from ..services.task_reports_service import task_reports_service
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

            # Создаем сессию БД и обрабатываем
            async for session in get_async_session():
                # Создаем TaskReport из webhook данных
                task_report = await task_reports_service.create_task_report_from_webhook(
                    session=session,
                    webhook_data=data
                )

                if not task_report:
                    # None means duplicate (already completed) - return success to prevent retries
                    bot_logger.info(
                        f"⏭️ Skipping notification for duplicate/completed task "
                        f"(plane_issue={data.get('plane_issue_id')})"
                    )
                    return web.json_response(
                        {'status': 'ignored', 'reason': 'Task already completed'},
                        status=200
                    )

                bot_logger.info(
                    f"✅ Created TaskReport #{task_report.id} for "
                    f"Plane issue {task_report.plane_sequence_id}"
                )

                # BUG FIX #4: Refresh task_report from database to get updated description
                # (create_task_report_from_webhook calls fetch_and_generate_report_from_plane
                # which updates task_description from Plane API and commits)
                await session.refresh(task_report)
                bot_logger.info(f"🔄 Refreshed task_report from DB, description length: {len(task_report.task_description) if task_report.task_description else 0}")

                # ✅ USE DATA FROM task_report (already fetched in create_task_report_from_webhook)
                # No duplicate Plane API calls needed - all data is in task_report

                # Отправляем уведомление админу (приоритет - кто закрыл)
                admin_to_notify = task_report.closed_by_telegram_id

                # Если не нашли кто закрыл - отправляем всем админам
                admin_list = [admin_to_notify] if admin_to_notify else settings.admin_user_id_list

                # Формируем сообщение
                autofill_notice = ""
                # Проверяем что report_text не пустой (минимум 100 символов)
                has_meaningful_content = task_report.report_text and len(task_report.report_text.strip()) > 100

                if task_report.auto_filled_from_journal and has_meaningful_content:
                    autofill_notice = "\n\n✅ _Отчёт автоматически заполнен из work journal_"
                elif task_report.report_text and has_meaningful_content:
                    autofill_notice = "\n\n✅ _Отчёт сгенерирован из комментариев Plane_"

                # Экранируем спецсимволы MarkdownV2
                def escape_md(text: str) -> str:
                    """Escape special characters for MarkdownV2"""
                    if not text:
                        return text
                    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
                    for char in special_chars:
                        text = text.replace(char, f'\\{char}')
                    return text

                task_title = escape_md(task_report.task_title or 'Не указано')
                closed_by = escape_md(task_report.closed_by_plane_name or 'Неизвестно')

                # Project name (from task_report.company - already mapped via COMPANY_MAPPING)
                project_line = ""
                if task_report.company:
                    project_line = f"**Проект:** {escape_md(task_report.company)}\n"

                # Workers/Assignees (from task_report.workers - already auto-filled)
                assignees_line = ""
                if task_report.workers:
                    try:
                        workers = json.loads(task_report.workers)
                        if isinstance(workers, list) and workers:
                            workers_text = ", ".join(workers)
                            assignees_line = f"**Исполнители:** {escape_md(workers_text)}\n"
                    except:
                        pass

                # Report text preview (if auto-generated)
                report_preview = ""
                if task_report.report_text and len(task_report.report_text.strip()) > 50:
                    report_text = task_report.report_text.strip()
                    # Truncate long reports
                    if len(report_text) > 200:
                        report_text = report_text[:197] + "..."
                    report_preview = f"\n**📝 Отчёт \\(preview\\):**\n_{escape_md(report_text)}_\n"

                # Build Plane task URL
                plane_url = f"https://plane.hhivp.com/hhivp/projects/{task_report.plane_project_id}/issues/{task_report.plane_issue_id}"
                plane_link = f"[Открыть в Plane]({plane_url})"

                # Проверяем наличие привязки к клиенту
                has_client = bool(task_report.client_chat_id)

                # Формируем информацию о клиенте
                if has_client and task_report.support_request:
                    # Получаем детали support_request для показа клиента
                    client_info = f"✅ Клиент: chat\\_id={task_report.client_chat_id}"
                else:
                    client_info = "⚠️ Клиент: не привязан к задаче"

                notification_text = (
                    f"📋 **Требуется отчёт о выполненной задаче\\!**\n\n"
                    f"**Задача:** \\#{task_report.plane_sequence_id}\n"
                    f"**Название:** {task_title}\n"
                    f"{project_line}"
                    f"{assignees_line}"
                    f"**Закрыл:** {closed_by}\n"
                    f"{client_info}\n"
                    f"{report_preview}"
                    f"\n{plane_link}{autofill_notice}"
                )

                # Кнопки - ВСЕГДА включают все опции
                keyboard_buttons = [
                    [InlineKeyboardButton(
                        text="📝 Заполнить/Редактировать отчёт",
                        callback_data=f"fill_report:{task_report.id}"
                    )]
                ]

                # Если есть готовый отчёт, добавляем кнопку просмотра
                if task_report.report_text:
                    keyboard_buttons.append([
                        InlineKeyboardButton(
                            text="👁️ Посмотреть отчёт",
                            callback_data=f"preview_report:{task_report.id}"
                        )
                    ])

                # ВСЕГДА добавляем кнопки одобрения
                if has_client:
                    # Если есть клиент - кнопка отправки
                    keyboard_buttons.append([
                        InlineKeyboardButton(
                            text="✅ Одобрить и отправить клиенту",
                            callback_data=f"approve_send:{task_report.id}"
                        )
                    ])

                # ВСЕГДА добавляем кнопку "закрыть без отправки"
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text="❌ Закрыть без отчёта клиенту",
                        callback_data=f"close_no_report:{task_report.id}"
                    )
                ])

                keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

                # Отправляем уведомление
                from aiogram.types import LinkPreviewOptions

                for admin_id in admin_list:
                    try:
                        await self.bot.send_message(
                            chat_id=admin_id,
                            text=notification_text,
                            reply_markup=keyboard,
                            parse_mode="MarkdownV2",
                            link_preview_options=LinkPreviewOptions(is_disabled=True)
                        )
                        bot_logger.info(
                            f"✅ Notified admin {admin_id} about TaskReport #{task_report.id}"
                        )
                    except Exception as e:
                        bot_logger.warning(
                            f"⚠️ Failed to notify admin {admin_id}: {e}"
                        )

                return web.json_response({
                    'status': 'processed',
                    'task_report_id': task_report.id,
                    'plane_sequence_id': task_report.plane_sequence_id
                })

        except json.JSONDecodeError:
            bot_logger.error("Invalid JSON in task-completed webhook")
            return web.json_response({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            # FIX (2026-01-20): Don't expose error details in response (security)
            # Log full error server-side only
            import traceback
            bot_logger.error(
                f"Error processing task-completed webhook: {e}",
                extra={"traceback": traceback.format_exc()}
            )
            # Return generic error to client
            return web.json_response(
                {'error': 'Internal server error'},
                status=500
            )

    async def handle_plane_direct_webhook(self, request: Request) -> Response:
        """
        Direct webhook from Plane (no n8n middleman)

        Plane sends raw webhook data, we filter and transform it here.
        This replaces the n8n "Plane Task Completed → Bot" workflow.

        Expected Plane webhook structure:
        {
            "event": "issue",
            "action": "updated",
            "data": {
                "id": "uuid",
                "sequence_id": 123,
                "project": "uuid",
                "name": "Task title",
                "description_stripped": "...",
                "completed_at": "2026-01-22T21:02:37Z",
                "state": {"group": "completed", "name": "Done"}
            },
            "activity": {
                "actor": {
                    "display_name": "D. Gusev",
                    "first_name": "Dmitriy",
                    "email": "user@example.com"
                }
            }
        }
        """
        try:
            # Verify Plane signature if secret is configured
            webhook_secret = getattr(settings, 'plane_webhook_secret', None)
            signature = request.headers.get('X-Plane-Signature')

            # TODO: Fix Plane signature verification later
            # For now, just log and accept (Plane's json.dumps format unclear)
            if signature:
                bot_logger.info(f"📨 Plane webhook with signature (verification skipped)")
            data = await request.json()

            # Log incoming webhook
            event = data.get('event', 'unknown')
            action = data.get('action', 'unknown')
            bot_logger.info(
                f"📨 Plane direct webhook: event={event}, action={action}"
            )

            # Route: comment on issue → lightweight notification
            if event == 'issue_comment' and action == 'created':
                return await self._notify_plane_event(data, event, action)

            # Only process issue events from here
            if event != 'issue':
                bot_logger.debug(f"⏭️ Ignoring: event={event}, action={action}")
                return web.json_response({'status': 'ignored', 'reason': f'Unhandled event: {event}'})

            issue_data = data.get('data', {})
            state = issue_data.get('state', {})
            state_group = state.get('group', '')

            # Route: new issue or non-completion update → lightweight notification
            if action == 'created' or state_group != 'completed':
                return await self._notify_plane_event(data, event, action)

            # TRANSFORM: Convert Plane format to our internal format
            # This replaces n8n "Transform Data" function
            activity = data.get('activity', {})
            actor = activity.get('actor', {})
            description = issue_data.get('description_stripped', '')

            # Extract support_request_id from description if present
            support_request_id = None
            import re
            match = re.search(r'support_request_id[=:\s]+(\d+)', description, re.IGNORECASE)
            if match:
                support_request_id = int(match.group(1))

            # Build payload in format expected by task_reports_service
            transformed_data = {
                'plane_issue_id': issue_data.get('id'),
                'plane_sequence_id': issue_data.get('sequence_id'),
                'plane_project_id': issue_data.get('project'),
                'task_title': issue_data.get('name'),
                'task_description': description,
                'closed_by': {
                    'display_name': actor.get('display_name'),
                    'first_name': actor.get('first_name'),
                    'email': actor.get('email')
                },
                'closed_at': issue_data.get('completed_at'),
                'support_request_id': support_request_id
            }

            bot_logger.info(
                f"✅ Transformed Plane webhook: "
                f"plane_issue={transformed_data['plane_issue_id']}, "
                f"seq_id={transformed_data['plane_sequence_id']}, "
                f"title={transformed_data['task_title'][:50] if transformed_data['task_title'] else 'N/A'}..."
            )

            # Process using existing task_reports logic
            # (reuse handle_task_completed_webhook logic)
            from ..services.task_reports_service import task_reports_service
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

            async for session in get_async_session():
                task_report = await task_reports_service.create_task_report_from_webhook(
                    session=session,
                    webhook_data=transformed_data
                )

                if not task_report:
                    bot_logger.info(
                        f"⏭️ Skipping notification for duplicate/completed task "
                        f"(plane_issue={transformed_data['plane_issue_id']})"
                    )
                    return web.json_response(
                        {'status': 'ignored', 'reason': 'Task already completed'},
                        status=200
                    )

                bot_logger.info(
                    f"✅ Created TaskReport #{task_report.id} for "
                    f"Plane issue #{task_report.plane_sequence_id}"
                )

                # Refresh to get auto-filled data
                await session.refresh(task_report)

                # Send notification to admin (same as handle_task_completed_webhook)
                admin_to_notify = task_report.closed_by_telegram_id
                admin_list = [admin_to_notify] if admin_to_notify else settings.admin_user_id_list

                # Build notification message
                def escape_md(text: str) -> str:
                    if not text:
                        return text
                    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
                    for char in special_chars:
                        text = text.replace(char, f'\\{char}')
                    return text

                task_title = escape_md(task_report.task_title or 'Не указано')
                closed_by = escape_md(task_report.closed_by_plane_name or 'Неизвестно')

                autofill_notice = ""
                has_meaningful_content = task_report.report_text and len(task_report.report_text.strip()) > 100
                if task_report.auto_filled_from_journal and has_meaningful_content:
                    autofill_notice = "\n\n✅ _Отчёт автоматически заполнен из work journal_"
                elif task_report.report_text and has_meaningful_content:
                    autofill_notice = "\n\n✅ _Отчёт сгенерирован из комментариев Plane_"

                notification_text = (
                    f"📋 *Задача завершена в Plane*\n\n"
                    f"*Задача:* \\#{task_report.plane_sequence_id} {task_title}\n"
                    f"*Закрыл:* {closed_by}{autofill_notice}\n\n"
                    f"_Нажмите кнопку для заполнения отчёта клиенту_"
                )

                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="📝 Заполнить отчёт",
                        callback_data=f"fill_report:{task_report.id}"
                    )],
                    [InlineKeyboardButton(
                        text="👁️ Предпросмотр",
                        callback_data=f"preview_report:{task_report.id}"
                    )],
                    [InlineKeyboardButton(
                        text="❌ Закрыть без отчёта",
                        callback_data=f"close_no_report:{task_report.id}"
                    )]
                ])

                from aiogram.types import LinkPreviewOptions
                for admin_id in admin_list:
                    try:
                        await self.bot.send_message(
                            chat_id=admin_id,
                            text=notification_text,
                            reply_markup=keyboard,
                            parse_mode="MarkdownV2",
                            link_preview_options=LinkPreviewOptions(is_disabled=True)
                        )
                        bot_logger.info(f"✅ Notified admin {admin_id} about TaskReport #{task_report.id}")
                    except Exception as e:
                        bot_logger.warning(f"⚠️ Failed to notify admin {admin_id}: {e}")

                return web.json_response({
                    'status': 'processed',
                    'task_report_id': task_report.id,
                    'plane_sequence_id': task_report.plane_sequence_id
                })

        except json.JSONDecodeError:
            bot_logger.error("Invalid JSON in plane-direct webhook")
            return web.json_response({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            import traceback
            bot_logger.error(
                f"Error processing plane-direct webhook: {e}",
                extra={"traceback": traceback.format_exc()}
            )
            return web.json_response({'error': 'Internal server error'}, status=500)

    # ==================== AI INTEGRATION WEBHOOKS ====================

    async def handle_ai_task_result(self, request: Request) -> Response:
        """
        Результат AI анализа сообщения на задачу от n8n.

        n8n присылает:
        {
            "source": "n8n_ai",
            "event_type": "task_detection_result",
            "timestamp": "...",
            "detection": {
                "is_task": true,
                "confidence": 85,  # 0-100%
                "task_data": {
                    "title": "Проверить бэкапы",
                    "description": "...",
                    "priority": "medium",
                    "due_date": null
                }
            },
            "original_message": {
                "chat_id": -1001234567890,
                "message_id": 123,
                "text": "...",
                "user_id": 123456,
                "user_name": "John"
            },
            "plane": {
                "project_id": "uuid",
                "project_name": "HHIVP"
            },
            "action_taken": "pending_confirmation" | "auto_created" | "ignored"
        }
        """
        try:
            # Verify signature
            webhook_secret = getattr(settings, 'n8n_webhook_secret', None)
            signature = request.headers.get('X-Webhook-Secret')

            if webhook_secret and signature:
                if signature != webhook_secret:
                    bot_logger.warning("Invalid AI task-result webhook signature")
                    return web.json_response({'error': 'Invalid signature'}, status=401)

            data = await request.json()

            bot_logger.info(
                f"📨 AI task-result webhook: "
                f"is_task={data.get('detection', {}).get('is_task')}, "
                f"confidence={data.get('detection', {}).get('confidence')}%, "
                f"action={data.get('action_taken')}"
            )

            detection = data.get('detection', {})
            original = data.get('original_message', {})
            plane = data.get('plane', {})
            action = data.get('action_taken')

            # Игнорируем если не задача
            if not detection.get('is_task'):
                return web.json_response({'status': 'ignored', 'reason': 'Not a task'})

            confidence = detection.get('confidence', 0)
            task_data = detection.get('task_data', {})

            # Store DetectedIssue for training data
            try:
                from ..services.chat_context_service import chat_context_service
                import json as json_lib
                await chat_context_service.store_detected_issue(
                    chat_id=original.get('chat_id', 0),
                    issue_type='task',
                    message_id=original.get('message_id'),
                    user_id=original.get('user_id'),
                    confidence=confidence / 100.0 if confidence > 1 else confidence,
                    title=task_data.get('title'),
                    description=task_data.get('description'),
                    original_text=original.get('text'),
                    ai_response_json=json_lib.dumps(detection, ensure_ascii=False, default=str),
                    ai_model_used=data.get('ai_model', 'n8n/openrouter')
                )
            except Exception as e:
                bot_logger.warning(f"Failed to store DetectedIssue for training: {e}")

            # ==== Авто-создание (высокая уверенность >= 75%) ====
            # Бот сам создаёт задачу с dedup check (не n8n)
            if action in ('auto_created', 'auto_create'):
                chat_id = original.get('chat_id')
                message_id = original.get('message_id')
                project_id = plane.get('project_id')

                if not chat_id or not project_id:
                    return web.json_response({'error': 'Missing chat_id or project_id'}, status=400)

                # Content hash dedup — skip exact duplicates in last 24h
                import hashlib
                normalized = (task_data.get('title', '') + original.get('text', '')).lower().strip()
                content_hash = hashlib.md5(normalized.encode()).hexdigest()[:16]

                dup_key = f"dedup:{chat_id}:{content_hash}"
                from ..services.redis_service import redis_service
                if await redis_service.exists(dup_key):
                    bot_logger.info(f"Duplicate detected (hash={content_hash}), skipping")
                    return web.json_response({'status': 'ignored', 'reason': 'duplicate'})
                await redis_service.set_json(dup_key, True, ttl=86400)  # 24h

                # Search for similar open issues
                from ..integrations.plane import plane_api
                similar = await plane_api.search_issues(project_id, task_data.get('title', ''), limit=3)

                if similar:
                    # Similar found — show buttons instead of auto-creating
                    cache_key = f"ai_task:{chat_id}:{message_id}"
                    await redis_service.set_json(cache_key, {
                        'task_data': task_data,
                        'plane': plane,
                        'original': original,
                        'confidence': confidence
                    }, ttl=900)

                    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                    buttons = []
                    for s in similar:
                        label = f"📎 #{s['sequence_id']} {s['name'][:35]}"
                        buttons.append([InlineKeyboardButton(
                            text=label,
                            callback_data=f"ai_add_comment:{chat_id}:{message_id}:{s['id'][:36]}"
                        )])
                    buttons.append([InlineKeyboardButton(
                        text="➕ Создать новую",
                        callback_data=f"ai_force_create:{chat_id}:{message_id}"
                    )])

                    try:
                        await self.bot.send_message(
                            chat_id=chat_id,
                            text=(
                                f"🔍 <b>AI обнаружил задачу (уверенность: {confidence}%)</b>\n\n"
                                f"📝 <b>{task_data.get('title', 'Без названия')}</b>\n\n"
                                f"<b>Похожие задачи:</b>\n"
                                + "\n".join(f"• #{s['sequence_id']} {s['name']}" for s in similar)
                                + "\n\n<i>Добавить коммент или создать новую?</i>"
                            ),
                            reply_to_message_id=message_id,
                            parse_mode="HTML",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
                        )
                    except Exception as e:
                        bot_logger.warning(f"Failed to send dedup notification: {e}")

                    return web.json_response({'status': 'processed', 'action': 'dedup_check'})

                # No duplicates — auto-create
                try:
                    description = (
                        f"<p><strong>Автоматически создано из сообщения в чате</strong></p>"
                        f"<p>{task_data.get('description', '')}</p>"
                        f"<hr/>"
                        f"<p><em>Автор: {original.get('user_name', 'Unknown')}</em></p>"
                    )
                    issue = await plane_api.create_issue(
                        project_id=project_id,
                        name=task_data.get('title', 'Задача из чата'),
                        description=description,
                        priority=task_data.get('priority', 'medium')
                    )

                    if issue and chat_id:
                        seq_id = issue.get('sequence_id', '?')

                        # Check if chat has notify_task_created enabled
                        should_notify = False
                        try:
                            from ..services.chat_context_service import chat_context_service
                            chat_settings = await chat_context_service.get_chat_settings(int(chat_id))
                            should_notify = chat_settings and getattr(chat_settings, 'notify_task_created', False)
                        except Exception:
                            pass

                        if should_notify:
                            await self.bot.send_message(
                                chat_id=chat_id,
                                text=(
                                    f"✅ Задача <b>#{seq_id}</b> создана в "
                                    f"<b>{plane.get('project_name', 'N/A')}</b>\n\n"
                                    f"📝 {task_data.get('title', 'Без названия')}"
                                ),
                                reply_to_message_id=message_id,
                                parse_mode="HTML"
                            )

                    return web.json_response({
                        'status': 'processed',
                        'action': 'auto_created',
                        'issue_id': issue.get('id') if issue else None
                    })
                except Exception as e:
                    bot_logger.error(f"Auto-create failed: {e}")
                    return web.json_response({'error': str(e)}, status=500)

            # ==== Требуется подтверждение (средняя уверенность 50-74%) ====
            elif action == 'pending_confirmation':
                chat_id = original.get('chat_id')
                message_id = original.get('message_id')
                user_id = original.get('user_id')

                if not chat_id:
                    return web.json_response({'error': 'No chat_id'}, status=400)

                # Формируем кнопки подтверждения
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                import json as json_lib

                # Сохраняем данные задачи в callback_data (ограничение 64 байта)
                # Используем кэш для больших данных
                cache_key = f"ai_task:{chat_id}:{message_id}"

                # Сохраняем в Redis cache
                from ..services.redis_service import redis_service
                await redis_service.set_json(cache_key, {
                    'task_data': task_data,
                    'plane': plane,
                    'original': original,
                    'confidence': confidence
                }, ttl=900)

                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="✅ Создать задачу",
                            callback_data=f"ai_confirm_task:{chat_id}:{message_id}"
                        ),
                        InlineKeyboardButton(
                            text="❌ Не задача",
                            callback_data=f"ai_reject_task:{chat_id}:{message_id}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="✏️ Редактировать",
                            callback_data=f"ai_edit_task:{chat_id}:{message_id}"
                        )
                    ]
                ])

                try:
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text=(
                            f"🤖 <b>AI обнаружил возможную задачу</b>\n\n"
                            f"📝 <b>{task_data.get('title', 'Без названия')}</b>\n"
                            f"📊 Проект: {plane.get('project_name', 'N/A')}\n"
                            f"🎯 Приоритет: {task_data.get('priority', 'medium')}\n\n"
                            f"<i>Уверенность: {confidence}%</i>\n\n"
                            f"Создать задачу в Plane?"
                        ),
                        reply_to_message_id=message_id,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    bot_logger.warning(f"Failed to send confirmation request: {e}")

                return web.json_response({
                    'status': 'processed',
                    'action': 'confirmation_sent'
                })

            # ==== Игнорируем (низкая уверенность < 50%) ====
            else:
                return web.json_response({'status': 'ignored', 'reason': 'Low confidence'})

        except json.JSONDecodeError:
            bot_logger.error("Invalid JSON in AI task-result webhook")
            return web.json_response({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            import traceback
            bot_logger.error(
                f"Error processing AI task-result webhook: {e}",
                extra={"traceback": traceback.format_exc()}
            )
            return web.json_response({'error': 'Internal server error'}, status=500)

    async def handle_ai_voice_result(self, request: Request) -> Response:
        """
        Результат обработки голосового сообщения от n8n.

        n8n присылает:
        {
            "source": "n8n_ai",
            "event_type": "voice_report_result",
            "timestamp": "...",
            "transcription": "Текст голосового сообщения",
            "extraction": {
                "task_found": true,
                "task": {
                    "plane_issue_id": "uuid",
                    "plane_sequence_id": 123,
                    "title": "Название задачи"
                },
                "duration_hours": 2.5,
                "travel_hours": 0.5,
                "workers": ["Имя1", "Имя2"],
                "company": "Компания",
                "work_description": "Что было сделано"
            },
            "action_taken": "report_created" | "task_not_found" | "pending_selection",
            "admin": {
                "telegram_id": 123456,
                "name": "Admin Name"
            },
            "chat_id": 123456,
            "original_message_id": 789
        }
        """
        try:
            # Verify signature
            webhook_secret = getattr(settings, 'n8n_webhook_secret', None)
            signature = request.headers.get('X-Webhook-Secret')

            if webhook_secret and signature:
                if signature != webhook_secret:
                    bot_logger.warning("Invalid AI voice-result webhook signature")
                    return web.json_response({'error': 'Invalid signature'}, status=401)

            data = await request.json()

            bot_logger.info(
                f"📨 AI voice-result webhook: "
                f"task_found={data.get('extraction', {}).get('task_found')}, "
                f"action={data.get('action_taken')}"
            )

            extraction = data.get('extraction', {})
            transcription = data.get('transcription', '')
            action = data.get('action_taken')
            admin = data.get('admin', {})
            chat_id = data.get('chat_id')
            original_message_id = data.get('original_message_id')

            admin_telegram_id = admin.get('telegram_id')
            if not admin_telegram_id:
                return web.json_response({'error': 'No admin telegram_id'}, status=400)

            # ==== Отчёт создан успешно ====
            if action == 'report_created':
                task = extraction.get('task', {})
                report = data.get('report', {})

                await self.bot.send_message(
                    chat_id=admin_telegram_id,
                    text=(
                        f"✅ <b>Голосовой отчёт обработан</b>\n\n"
                        f"📝 <b>Задача:</b> #{task.get('plane_sequence_id')} {task.get('title', 'N/A')}\n"
                        f"⏱ <b>Длительность:</b> {extraction.get('duration_hours', 0)} ч\n"
                        f"🚗 <b>Дорога:</b> {extraction.get('travel_hours', 0)} ч\n"
                        f"👥 <b>Исполнители:</b> {', '.join(extraction.get('workers', []))}\n"
                        f"🏢 <b>Компания:</b> {extraction.get('company', 'N/A')}\n\n"
                        f"📋 <b>Описание работ:</b>\n"
                        f"<i>{extraction.get('work_description', transcription[:200])}</i>\n\n"
                        f"{'✅ Отчёт отправлен клиенту' if report.get('sent_to_client') else '📝 Отчёт создан (требуется отправка)'}"
                    ),
                    parse_mode="HTML"
                )

                return web.json_response({
                    'status': 'processed',
                    'action': 'report_created'
                })

            # ==== Задача не найдена - показываем поиск ====
            elif action == 'task_not_found':
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

                # Сохраняем данные для выбора задачи
                cache_key = f"voice_task_select:{admin_telegram_id}:{original_message_id}"
                from ..services.redis_service import redis_service as _rs
                await _rs.set_json(cache_key, {
                    'transcription': transcription,
                    'extraction': extraction
                }, ttl=900)

                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🔍 Найти задачу вручную",
                            callback_data=f"voice_find_task:{admin_telegram_id}:{original_message_id}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="📝 Создать новую задачу",
                            callback_data=f"voice_new_task:{admin_telegram_id}:{original_message_id}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="❌ Отмена",
                            callback_data=f"voice_cancel:{admin_telegram_id}:{original_message_id}"
                        )
                    ]
                ])

                await self.bot.send_message(
                    chat_id=admin_telegram_id,
                    text=(
                        f"⚠️ <b>Задача не найдена автоматически</b>\n\n"
                        f"🎤 <b>Транскрипция:</b>\n"
                        f"<i>{transcription[:300]}{'...' if len(transcription) > 300 else ''}</i>\n\n"
                        f"📊 <b>Извлечённые данные:</b>\n"
                        f"⏱ Длительность: {extraction.get('duration_hours', '?')} ч\n"
                        f"👥 Исполнители: {', '.join(extraction.get('workers', ['?']))}\n"
                        f"🏢 Компания: {extraction.get('company', '?')}\n\n"
                        f"Выберите действие:"
                    ),
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )

                return web.json_response({
                    'status': 'processed',
                    'action': 'selection_requested'
                })

            # ==== Несколько задач найдено - выбор ====
            elif action == 'pending_selection':
                candidates = data.get('task_candidates', [])
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

                # Сохраняем данные
                cache_key = f"voice_task_select:{admin_telegram_id}:{original_message_id}"
                from ..services.redis_service import redis_service as _rs2
                await _rs2.set_json(cache_key, {
                    'transcription': transcription,
                    'extraction': extraction,
                    'candidates': candidates
                }, ttl=900)

                # Создаём кнопки для каждой задачи-кандидата
                buttons = []
                for i, candidate in enumerate(candidates[:5]):  # Максимум 5 кандидатов
                    buttons.append([
                        InlineKeyboardButton(
                            text=f"#{candidate.get('sequence_id')} {candidate.get('title', 'N/A')[:30]}",
                            callback_data=f"voice_select:{admin_telegram_id}:{original_message_id}:{i}"
                        )
                    ])

                buttons.append([
                    InlineKeyboardButton(
                        text="🔍 Другая задача",
                        callback_data=f"voice_find_task:{admin_telegram_id}:{original_message_id}"
                    )
                ])
                buttons.append([
                    InlineKeyboardButton(
                        text="❌ Отмена",
                        callback_data=f"voice_cancel:{admin_telegram_id}:{original_message_id}"
                    )
                ])

                keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

                await self.bot.send_message(
                    chat_id=admin_telegram_id,
                    text=(
                        f"🔍 <b>Найдено несколько задач</b>\n\n"
                        f"🎤 <b>Транскрипция:</b>\n"
                        f"<i>{transcription[:200]}{'...' if len(transcription) > 200 else ''}</i>\n\n"
                        f"Выберите задачу для отчёта:"
                    ),
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )

                return web.json_response({
                    'status': 'processed',
                    'action': 'selection_requested'
                })

            return web.json_response({'status': 'ignored', 'reason': 'Unknown action'})

        except json.JSONDecodeError:
            bot_logger.error("Invalid JSON in AI voice-result webhook")
            return web.json_response({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            import traceback
            bot_logger.error(
                f"Error processing AI voice-result webhook: {e}",
                extra={"traceback": traceback.format_exc()}
            )
            return web.json_response({'error': 'Internal server error'}, status=500)

    async def _notify_plane_event(self, data: dict, event: str, action: str) -> Response:
        """Send lightweight Plane event notification to relevant users.

        Handles: new comments, new issues, non-completion updates.
        Rate-limits non-comment updates to 1 per issue per 5 min.
        """
        issue_data = data.get('data', {})
        activity = data.get('activity', {})
        actor = activity.get('actor', {})
        actor_name = actor.get('display_name', actor.get('first_name', ''))
        actor_email = actor.get('email', '')

        def esc(t):
            return str(t).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;') if t else ''

        # Build notification based on event type
        if event == 'issue_comment':
            issue_detail = issue_data.get('issue_detail', {})
            seq_id = issue_detail.get('sequence_id', issue_data.get('sequence_id', '?'))
            title = issue_detail.get('name', issue_data.get('name', ''))
            comment = issue_data.get('comment_stripped', '')[:200]
            notification = (
                f"💬 Комментарий к <b>#{seq_id}</b> {esc(title[:60])}\n\n"
                f"<i>{esc(comment)}</i>\n"
                f"— {esc(actor_name)}"
            )
        elif action == 'created':
            seq_id = issue_data.get('sequence_id', '?')
            title = issue_data.get('name', '')
            priority = issue_data.get('priority', '')
            prio_icon = {'urgent': '🔴 ', 'high': '🟠 '}.get(priority, '')
            notification = f"📋 Новая задача <b>#{seq_id}</b>\n<b>{esc(title[:80])}</b>"
            if priority and priority != 'none':
                notification += f"\n{prio_icon}{priority}"
            notification += f"\n— {esc(actor_name)}"
        else:
            # Issue updated (non-completion)
            seq_id = issue_data.get('sequence_id', '?')
            title = issue_data.get('name', '')
            state_name = issue_data.get('state', {}).get('name', '')
            priority = issue_data.get('priority', '')
            parts = []
            if state_name:
                parts.append(state_name)
            if priority in ('urgent', 'high'):
                parts.append(f"⚡ {priority}")
            detail = " | ".join(parts)
            notification = f"🔄 <b>#{seq_id}</b> {esc(title[:60])}"
            if detail:
                notification += f"\n{esc(detail)}"
            notification += f"\n— {esc(actor_name)}"

        # Rate limit non-comment updates (max 1 per issue per 5 min)
        if event != 'issue_comment':
            from ..services.redis_service import redis_service
            rate_key = f"plane_notif:{seq_id}"
            if await redis_service.exists(rate_key):
                bot_logger.debug(f"⏭️ Rate limited notification for #{seq_id}")
                return web.json_response({'status': 'rate_limited'})
            await redis_service.set_json(rate_key, True, ttl=300)

        # Resolve recipients: assignees → Telegram IDs, exclude actor
        recipients = set()
        try:
            assignees = issue_data.get('assignees', [])
            if not assignees and event == 'issue_comment':
                assignees = issue_data.get('issue_detail', {}).get('assignees', [])

            if assignees:
                async for session in get_async_session():
                    from ..services.plane_mappings_service import PlaneMappingsService
                    svc = PlaneMappingsService(session)
                    for a in assignees:
                        ident = (a.get('email') or a.get('display_name', '')) if isinstance(a, dict) else str(a)
                        if ident:
                            tid = await svc.get_telegram_id(ident)
                            if tid:
                                recipients.add(tid)
                    # Exclude actor (don't notify yourself)
                    if actor_email:
                        actor_tid = await svc.get_telegram_id(actor_email)
                        if actor_tid:
                            recipients.discard(actor_tid)
        except Exception as e:
            bot_logger.debug(f"Could not resolve Plane notification recipients: {e}")

        if not recipients:
            recipients = set(settings.admin_user_id_list)

        # Send notifications
        from aiogram.types import LinkPreviewOptions
        sent = 0
        for rid in recipients:
            try:
                await self.bot.send_message(
                    chat_id=rid,
                    text=notification.strip(),
                    parse_mode="HTML",
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )
                sent += 1
            except Exception as e:
                bot_logger.warning(f"Failed to send Plane notification to {rid}: {e}")

        bot_logger.info(f"📨 Plane event {event}/{action} #{seq_id}: notified {sent} users")
        return web.json_response({'status': 'notified', 'event': event, 'action': action, 'recipients': sent})

    def _verify_signature(self, payload: str, signature: str, secret: str) -> bool:
        """Проверка подписи webhook"""
        if not signature:
            return False

        # Вычисляем ожидаемую подпись
        expected_signature = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()

        # Plane sends just hex, n8n sends sha256=hex - check both formats
        return (
            hmac.compare_digest(expected_signature, signature) or
            hmac.compare_digest(f"sha256={expected_signature}", signature)
        )
    
    async def start_server(self, host: str = '0.0.0.0', port: int = 8080):
        """Запуск webhook сервера"""
        bot_logger.info(f"Starting webhook server on {host}:{port}")
        
        runner = web.AppRunner(self.app)
        await runner.setup()
        
        site = web.TCPSite(runner, host, port)
        await site.start()
        
        bot_logger.info(f"Webhook server started on http://{host}:{port}")
        return runner
