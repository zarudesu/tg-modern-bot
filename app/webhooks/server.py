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
            data = await request.json()

            # Log incoming webhook
            event = data.get('event', 'unknown')
            action = data.get('action', 'unknown')
            bot_logger.info(
                f"📨 Plane direct webhook: event={event}, action={action}"
            )

            # FILTER: Only process issue updates with completed state
            # This replaces n8n "Filter: Only Done State Changes" function
            if event != 'issue' or action != 'updated':
                bot_logger.debug(f"⏭️ Ignoring: event={event}, action={action}")
                return web.json_response({'status': 'ignored', 'reason': 'Not issue update'})

            issue_data = data.get('data', {})
            state = issue_data.get('state', {})
            state_group = state.get('group', '')

            if state_group != 'completed':
                bot_logger.debug(f"⏭️ Ignoring: state.group={state_group} (not completed)")
                return web.json_response({'status': 'ignored', 'reason': 'Not completed state'})

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

        # Проверяем подпись
        return hmac.compare_digest(f"sha256={expected_signature}", signature)
    
    async def start_server(self, host: str = '0.0.0.0', port: int = 8080):
        """Запуск webhook сервера"""
        bot_logger.info(f"Starting webhook server on {host}:{port}")
        
        runner = web.AppRunner(self.app)
        await runner.setup()
        
        site = web.TCPSite(runner, host, port)
        await site.start()
        
        bot_logger.info(f"Webhook server started on http://{host}:{port}")
        return runner
