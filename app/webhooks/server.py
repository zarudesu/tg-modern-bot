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
        # self.app.router.add_post('/webhooks/plane', self.handle_plane_webhook)
        # self.app.router.add_post('/webhooks/plane-n8n', self.handle_plane_n8n_webhook)
        self.app.router.add_post('/webhooks/task-completed', self.handle_task_completed_webhook)
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
                '/webhooks/task-completed - Task completion reports (from n8n)',
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
            # Получаем данные
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

                # 📥 FETCH PLANE DATA (comments, assignees, priority, project name)
                from ..integrations.plane import plane_api

                plane_details = None
                plane_comments = []
                plane_project_name = None

                if plane_api.configured and task_report.plane_project_id and task_report.plane_issue_id:
                    try:
                        bot_logger.info(f"📥 Fetching Plane details for notification...")

                        # Fetch issue details (assignees, priority, state, labels)
                        plane_details = await plane_api.get_issue_details(
                            project_id=task_report.plane_project_id,
                            issue_id=task_report.plane_issue_id
                        )

                        # Fetch comments
                        plane_comments = await plane_api.get_issue_comments(
                            project_id=task_report.plane_project_id,
                            issue_id=task_report.plane_issue_id
                        )

                        # Get project name from cached projects list
                        projects = await plane_api.get_all_projects()
                        project_match = next((p for p in projects if p['id'] == task_report.plane_project_id), None)
                        if project_match:
                            plane_project_name = project_match['name']

                        bot_logger.info(
                            f"✅ Fetched Plane data: {len(plane_comments)} comments, "
                            f"project={plane_project_name}, priority={plane_details.get('priority') if plane_details else None}"
                        )
                    except Exception as e:
                        bot_logger.warning(f"⚠️ Failed to fetch Plane data for notification: {e}")

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

                # Project name (from Plane API or webhook data)
                project_name = plane_project_name or data.get('project_name', '')
                project_line = f"**Проект:** {escape_md(project_name)}\n" if project_name else ""

                # Priority from Plane (if available)
                priority_line = ""
                if plane_details and plane_details.get('priority'):
                    priority_map = {
                        'urgent': '🔴 Срочно',
                        'high': '🟠 Высокий',
                        'medium': '🟡 Средний',
                        'low': '🟢 Низкий',
                        'none': '⚪ Не указан'
                    }
                    priority_text = priority_map.get(plane_details['priority'], plane_details['priority'])
                    priority_line = f"**Приоритет:** {escape_md(priority_text)}\n"

                # Assignees from Plane (if available)
                assignees_line = ""
                if plane_details and plane_details.get('assignee_details'):
                    assignees = plane_details['assignee_details']
                    if isinstance(assignees, list) and assignees:
                        assignee_names = [
                            assignee.get('display_name') or assignee.get('first_name', 'Unknown')
                            for assignee in assignees
                        ]
                        assignees_text = ", ".join(assignee_names)
                        assignees_line = f"**Исполнители:** {escape_md(assignees_text)}\n"

                # Task description preview
                description_preview = ""
                if task_report.task_description and len(task_report.task_description.strip()) > 10:
                    desc_text = task_report.task_description.strip()
                    # Truncate long descriptions
                    if len(desc_text) > 150:
                        desc_text = desc_text[:147] + "..."
                    description_preview = f"\n**📄 Описание:**\n_{escape_md(desc_text)}_\n"

                # Comments preview (first 3 comments)
                comments_preview = ""
                if plane_comments:
                    comments_preview = f"\n**💬 Комментарии \\({len(plane_comments)}\\):**\n"
                    for idx, comment in enumerate(plane_comments[:3], 1):
                        # Try both 'comment_html' and 'comment' fields
                        comment_html = comment.get('comment_html', '').strip()
                        comment_text = comment.get('comment', '').strip()

                        # Prefer comment_html, fallback to comment
                        text_to_show = comment_html or comment_text

                        if text_to_show:
                            # Strip HTML tags from comment_html
                            import re
                            text_to_show = re.sub(r'<[^>]+>', '', text_to_show).strip()

                            # Truncate long comments
                            if len(text_to_show) > 100:
                                text_to_show = text_to_show[:97] + "..."

                            actor_detail = comment.get('actor_detail', {})
                            actor_name = (
                                actor_detail.get('display_name') or
                                actor_detail.get('first_name') or
                                'Unknown'
                            )
                            comments_preview += f"{idx}\\. _{escape_md(actor_name)}_: {escape_md(text_to_show)}\n"

                    if len(plane_comments) > 3:
                        comments_preview += f"_\\.\\.\\. и ещё {len(plane_comments) - 3} комментариев_\n"

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
                    f"{priority_line}"
                    f"{assignees_line}"
                    f"**Закрыл:** {closed_by}\n"
                    f"{client_info}\n"
                    f"{description_preview}"
                    f"{comments_preview}"
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
            bot_logger.error(f"Error processing task-completed webhook: {e}")
            import traceback
            bot_logger.error(traceback.format_exc())
            return web.json_response(
                {'error': 'Internal server error', 'details': str(e)},
                status=500
            )

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
