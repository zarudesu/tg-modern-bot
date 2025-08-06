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
from ..integrations.plane_with_mentions import PlaneNotificationService, PlaneWebhookPayload
from ..services.plane_n8n_handler import PlaneN8nHandler, PlaneWebhookData
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
        self.app.router.add_post('/webhooks/plane', self.handle_plane_webhook)
        self.app.router.add_post('/webhooks/plane-n8n', self.handle_plane_n8n_webhook)
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
                '/webhooks/plane - Plane.com direct webhooks',
                '/webhooks/plane-n8n - Plane notifications from n8n',
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
