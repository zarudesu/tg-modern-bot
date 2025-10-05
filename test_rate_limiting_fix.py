#!/usr/bin/env python3
"""
Тест исправлений rate limiting для Plane API
"""

import asyncio
import time
from app.integrations.plane_api import PlaneAPIClient

async def test_rate_limiting():
    """Тестирование rate limiting исправлений"""
    
    print("🧪 Тестирование исправлений rate limiting для Plane API")
    print("=" * 60)
    
    # Создаем экземпляр клиента
    client = PlaneAPIClient()
    
    # Проверяем статус rate limiting
    print("📊 Начальный статус rate limiting:")
    status = client.get_rate_limit_status()
    for key, value in status.items():
        print(f"  {key}: {value}")
    
    print("\n🔧 Проверяем конфигурацию:")
    print(f"  Request delay: {client._request_delay}s (должно быть 1.0s для 60 req/min)")
    print(f"  API configured: {client.configured}")
    
    if not client.configured:
        print("❌ Plane API не настроен - проверьте переменные окружения")
        return
    
    print("\n🌐 Тестирование подключения...")
    start_time = time.time()
    
    try:
        # Тестируем подключение
        result = await client.test_connection()
        end_time = time.time()
        
        print(f"⏱️  Время выполнения: {end_time - start_time:.2f}s")
        
        if result['success']:
            print("✅ Подключение успешно!")
            print(f"  Workspace: {result.get('workspace')}")
            print(f"  Projects: {result.get('projects_count')}")
            print(f"  API Version: {result.get('api_version')}")
        else:
            print(f"❌ Ошибка подключения: {result.get('error')}")
            
    except Exception as e:
        print(f"❌ Исключение при тестировании: {e}")
    
    # Проверяем статус после запроса
    print("\n📊 Статус rate limiting после запроса:")
    status = client.get_rate_limit_status()
    for key, value in status.items():
        print(f"  {key}: {value}")
    
    print("\n✅ Тест завершен")
    
    # Тестируем множественные запросы
    if client.configured:
        print("\n🔄 Тестирование множественных запросов (3 запроса)...")
        
        for i in range(3):
            start = time.time()
            try:
                result = await client.test_connection()
                end = time.time()
                print(f"  Запрос {i+1}: {end - start:.2f}s - {'✅' if result['success'] else '❌'}")
                
                status = client.get_rate_limit_status()
                print(f"    Remaining: {status['remaining']}, Reset in: {status['reset_in_seconds']:.1f}s")
                
            except Exception as e:
                print(f"  Запрос {i+1}: ❌ Ошибка - {e}")

if __name__ == "__main__":
    asyncio.run(test_rate_limiting())