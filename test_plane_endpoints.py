#!/usr/bin/env python3
"""
Тест различных Plane API endpoints для поиска правильного пути
"""
import asyncio
import aiohttp
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def test_plane_endpoints():
    """Тестирование различных endpoint'ов Plane API"""
    base_url = "https://plane.hhivp.com"
    api_token = "plane_api_15504fe9f81f4a819a79ff8409135447"
    workspace_slug = "hhivp"
    
    headers = {
        'X-API-Key': api_token,
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    # Возможные пути API
    test_urls = [
        f"{base_url}/api/workspaces/{workspace_slug}/",
        f"{base_url}/api/v1/workspaces/{workspace_slug}/",
        f"{base_url}/api/public/workspaces/{workspace_slug}/",
        f"{base_url}/api/workspaces/",
        f"{base_url}/api/v1/workspaces/",
        f"{base_url}/api/public/workspaces/",
        f"{base_url}/api/",
        f"{base_url}/api/v1/",
        f"{base_url}/api/public/",
    ]
    
    async with aiohttp.ClientSession() as session:
        for url in test_urls:
            try:
                print(f"🔄 Тестируем: {url}")
                
                async with session.get(url, headers=headers) as response:
                    status = response.status
                    content_type = response.headers.get('content-type', 'unknown')
                    
                    if status == 200:
                        try:
                            data = await response.json()
                            print(f"✅ {status} - Success! Response keys: {list(data.keys()) if isinstance(data, dict) else 'List with ' + str(len(data)) + ' items'}")
                        except:
                            text = await response.text()
                            print(f"✅ {status} - Success! Text response (first 100 chars): {text[:100]}...")
                    elif status == 401:
                        print(f"🔑 {status} - Unauthorized (API key issue)")
                    elif status == 403:
                        print(f"🚫 {status} - Forbidden (no access)")
                    elif status == 404:
                        print(f"❌ {status} - Not Found")
                    else:
                        try:
                            text = await response.text()
                            print(f"⚠️ {status} - {text[:100]}...")
                        except:
                            print(f"⚠️ {status} - Unknown error")
                            
            except Exception as e:
                print(f"💥 Error: {str(e)}")
            
            print()
            
    # Также попробуем альтернативные методы аутентификации
    print("🔄 Тестируем альтернативные методы аутентификации...")
    alt_headers = [
        {'Authorization': f'Bearer {api_token}', 'Content-Type': 'application/json'},
        {'Authorization': f'Token {api_token}', 'Content-Type': 'application/json'},
        {'Authorization': f'ApiKey {api_token}', 'Content-Type': 'application/json'},
    ]
    
    test_url = f"{base_url}/api/workspaces/"
    
    for i, alt_header in enumerate(alt_headers, 1):
        try:
            print(f"🔄 Auth method {i}: {list(alt_header.keys())}")
            
            async with session.get(test_url, headers=alt_header) as response:
                status = response.status
                print(f"   {status} - {'✅ Success' if status == 200 else '❌ Failed'}")
                
        except Exception as e:
            print(f"   💥 Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_plane_endpoints())