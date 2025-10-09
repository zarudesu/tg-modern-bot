#!/usr/bin/env python3
"""
Тест доступности Plane веб-интерфейса и поиск API документации
"""
import asyncio
import aiohttp
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def test_plane_web():
    """Тестирование веб-интерфейса и поиск API путей"""
    base_url = "https://plane.hhivp.com"
    
    # Тестируем различные страницы
    test_urls = [
        f"{base_url}/",                      # Главная страница
        f"{base_url}/api/",                  # API корень
        f"{base_url}/docs/",                 # Документация
        f"{base_url}/swagger/",              # Swagger
        f"{base_url}/api-docs/",             # API документация
        f"{base_url}/openapi/",              # OpenAPI
        f"{base_url}/.well-known/",          # Well-known
        f"{base_url}/health/",               # Health check
        f"{base_url}/ping/",                 # Ping
        f"{base_url}/status/",               # Status
        f"{base_url}/auth/",                 # Auth
        f"{base_url}/login/",                # Login
    ]
    
    async with aiohttp.ClientSession() as session:
        for url in test_urls:
            try:
                print(f"🔄 {url}")
                
                async with session.get(url, allow_redirects=False) as response:
                    status = response.status
                    content_type = response.headers.get('content-type', 'unknown')
                    location = response.headers.get('location', '')
                    
                    if status == 200:
                        if 'json' in content_type:
                            try:
                                data = await response.json()
                                print(f"   ✅ {status} - JSON response")
                                if isinstance(data, dict):
                                    print(f"      🔑 Keys: {list(data.keys())}")
                                elif isinstance(data, list):
                                    print(f"      📋 List with {len(data)} items")
                            except:
                                text = await response.text()
                                print(f"   ✅ {status} - JSON parse failed: {text[:100]}...")
                        elif 'html' in content_type:
                            text = await response.text()
                            print(f"   ✅ {status} - HTML page ({len(text)} chars)")
                            # Ищем упоминания API в HTML
                            if 'api' in text.lower():
                                print(f"      🔍 Contains API references")
                        else:
                            text = await response.text()
                            print(f"   ✅ {status} - {content_type}: {text[:50]}...")
                    elif status in [301, 302, 303, 307, 308]:
                        print(f"   🔄 {status} - Redirect to: {location}")
                    elif status == 401:
                        print(f"   🔑 {status} - Unauthorized")
                    elif status == 403:
                        print(f"   🚫 {status} - Forbidden")
                    elif status == 404:
                        print(f"   ❌ {status} - Not Found")
                    else:
                        print(f"   ⚠️ {status} - {content_type}")
                        
            except Exception as e:
                print(f"   💥 Error: {str(e)}")
                
        print()
        print("🔍 Проверяем конкретные API эндпоинты без аутентификации...")
        
        # Проверяем эндпоинты которые могут быть публичными
        public_endpoints = [
            f"{base_url}/api/v1/",
            f"{base_url}/api/public/",
            f"{base_url}/api/health/",
            f"{base_url}/api/ping/",
            f"{base_url}/api/version/",
            f"{base_url}/api/config/",
        ]
        
        for url in public_endpoints:
            try:
                print(f"🔄 {url}")
                
                async with session.get(url) as response:
                    status = response.status
                    if status == 200:
                        try:
                            data = await response.json()
                            print(f"   ✅ {status} - SUCCESS!")
                            print(f"      📋 Data: {data}")
                        except:
                            text = await response.text()
                            print(f"   ✅ {status} - Response: {text[:100]}...")
                    else:
                        print(f"   ❌ {status}")
                        
            except Exception as e:
                print(f"   💥 Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_plane_web())