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
                    bot_logger.error("Failed to create TaskReport from webhook")
                    return web.json_response(
                        {'error': 'Failed to create task report'},
                        status=500
                    )

                bot_logger.info(
                    f"✅ Created TaskReport #{task_report.id} for "
                    f"Plane issue {task_report.plane_sequence_id}"
                )

                # Отправляем уведомление админу (приоритет - кто закрыл)
                admin_to_notify = task_report.closed_by_telegram_id

                # Если не нашли кто закрыл - отправляем всем админам
                admin_list = [admin_to_notify] if admin_to_notify else settings.admin_user_id_list

                # Формируем сообщение
                autofill_notice = ""
                if task_report.auto_filled_from_journal:
                    autofill_notice = "\\n\\n✅ _Отчёт автоматически заполнен из work journal_"

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

                notification_text = (
                    f"📋 **Требуется отчёт о выполненной задаче\\!**\\n\\n"
                    f"**Задача:** \\#{task_report.plane_sequence_id}\\n"
                    f"**Название:** {task_title}\\n"
                    f"**Закрыл:** {closed_by}{autofill_notice}"
                )

                # Кнопки
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="📝 Заполнить отчёт",
                        callback_data=f"fill_report:{task_report.id}"
                    )],
                    # [InlineKeyboardButton(
                    #     text="⚡ Пропустить (авто)",
                    #     callback_data=f"skip_report:{task_report.id}"
                    # )]  # TODO: Disabled for now
                ])

                # Отправляем уведомление
                for admin_id in admin_list:
                    try:
                        await self.bot.send_message(
                            chat_id=admin_id,
                            text=notification_text,
                            reply_markup=keyboard,
                            parse_mode="MarkdownV2"
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
