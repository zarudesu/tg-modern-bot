#!/usr/bin/env python3
"""
Тест современного Plane API с правильными путями
"""
import asyncio
import aiohttp
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def test_modern_plane_api():
    """Тестирование современных API путей Plane"""
    base_url = "https://plane.hhivp.com"
    api_token = "plane_api_15504fe9f81f4a819a79ff8409135447"
    workspace_slug = "hhivp"
    
    # Современные Plane API пути (основано на официальной документации)
    test_endpoints = [
        # Workspace info
        f"{base_url}/api/v1/workspaces/{workspace_slug}/",
        f"{base_url}/api/workspaces/{workspace_slug}/",
        
        # Members/Users
        f"{base_url}/api/v1/workspaces/{workspace_slug}/workspace-members/",
        f"{base_url}/api/workspaces/{workspace_slug}/workspace-members/", 
        f"{base_url}/api/v1/workspaces/{workspace_slug}/members/",
        f"{base_url}/api/workspaces/{workspace_slug}/members/",
        
        # Issues/Tasks  
        f"{base_url}/api/v1/workspaces/{workspace_slug}/issues/",
        f"{base_url}/api/workspaces/{workspace_slug}/issues/",
        f"{base_url}/api/v1/workspaces/{workspace_slug}/my-issues/",
        f"{base_url}/api/workspaces/{workspace_slug}/my-issues/",
        
        # Projects
        f"{base_url}/api/v1/workspaces/{workspace_slug}/projects/",
        f"{base_url}/api/workspaces/{workspace_slug}/projects/",
        
        # User profile endpoints
        f"{base_url}/api/v1/users/me/",
        f"{base_url}/api/users/me/",
        
        # General endpoints
        f"{base_url}/api/v1/workspaces/",
        f"{base_url}/api/workspaces/",
    ]
    
    headers = {
        'X-API-Key': api_token,
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    async with aiohttp.ClientSession() as session:
        print("🔍 Тестируем современные Plane API endpoints...")
        print("=" * 60)
        
        for endpoint in test_endpoints:
            try:
                print(f"🔄 {endpoint}")
                
                async with session.get(endpoint, headers=headers) as response:
                    status = response.status
                    content_type = response.headers.get('content-type', '')
                    
                    if status == 200:
                        try:
                            data = await response.json()
                            print(f"   ✅ {status} - SUCCESS!")
                            
                            if isinstance(data, dict):
                                keys = list(data.keys())[:10]  # Первые 10 ключей
                                print(f"      📋 Keys: {keys}")
                                
                                # Особенно интересные поля для workspace
                                if 'name' in data:
                                    print(f"      🏢 Name: {data['name']}")
                                if 'id' in data:
                                    print(f"      🆔 ID: {data['id']}")
                                if 'slug' in data:
                                    print(f"      🔗 Slug: {data['slug']}")
                                    
                            elif isinstance(data, list):
                                print(f"      📋 List with {len(data)} items")
                                if data and isinstance(data[0], dict):
                                    first_keys = list(data[0].keys())[:5]
                                    print(f"      📋 First item keys: {first_keys}")
                            
                            # Это успешный endpoint - используем его для дальнейших тестов
                            if 'issues' in endpoint.lower():
                                print(f"      🎯 НАЙДЕН РАБОЧИЙ ENDPOINT ДЛЯ ЗАДАЧ!")
                            elif 'members' in endpoint.lower():
                                print(f"      🎯 НАЙДЕН РАБОЧИЙ ENDPOINT ДЛЯ УЧАСТНИКОВ!")
                            elif 'workspaces' in endpoint.lower() and f'/{workspace_slug}/' in endpoint:
                                print(f"      🎯 НАЙДЕН РАБОЧИЙ ENDPOINT ДЛЛ WORKSPACE!")
                                
                        except Exception as e:
                            text = await response.text()
                            print(f"   ✅ {status} - SUCCESS (non-JSON): {text[:100]}...")
                            
                    elif status == 401:
                        print(f"   🔑 {status} - Unauthorized (проверить токен)")
                    elif status == 403:
                        print(f"   🚫 {status} - Forbidden (нет прав доступа)")
                    elif status == 404:
                        print(f"   ❌ {status} - Not Found")
                    elif status == 500:
                        print(f"   💥 {status} - Server Error")
                    else:
                        try:
                            text = await response.text()
                            print(f"   ⚠️ {status} - {text[:50]}...")
                        except:
                            print(f"   ⚠️ {status}")
                            
            except Exception as e:
                print(f"   💥 Connection Error: {str(e)}")
                
        print()
        print("🔍 Дополнительная проверка с альтернативными заголовками...")
        
        # Тестируем самый перспективный endpoint с разными заголовками
        test_endpoint = f"{base_url}/api/v1/users/me/"
        
        alt_headers_list = [
            {'X-API-Key': api_token, 'Content-Type': 'application/json'},
            {'Authorization': f'Bearer {api_token}', 'Content-Type': 'application/json'},
            {'Authorization': f'Token {api_token}', 'Content-Type': 'application/json'},
        ]
        
        for i, alt_headers in enumerate(alt_headers_list, 1):
            try:
                print(f"   🔄 Заголовки {i}: {list(alt_headers.keys())}")
                
                async with session.get(test_endpoint, headers=alt_headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"      ✅ SUCCESS! User info: {data.get('email', 'N/A')}")
                        break
                    else:
                        print(f"      ❌ {response.status}")
                        
            except Exception as e:
                print(f"      💥 {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_modern_plane_api())