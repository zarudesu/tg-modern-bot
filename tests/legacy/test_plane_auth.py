#!/usr/bin/env python3
"""
Тест различных методов аутентификации Plane API
"""
import asyncio
import aiohttp
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def test_plane_auth():
    """Тестирование различных методов аутентификации"""
    base_url = "https://plane.hhivp.com"
    api_token = "plane_api_15504fe9f81f4a819a79ff8409135447"
    workspace_slug = "hhivp"
    
    # Различные методы аутентификации
    auth_methods = [
        ("X-API-Key", f"{api_token}"),
        ("Authorization", f"Bearer {api_token}"),
        ("Authorization", f"Token {api_token}"),
        ("Authorization", f"ApiKey {api_token}"),
        ("Authorization", f"API-Key {api_token}"),
        ("X-Auth-Token", f"{api_token}"),
        ("Api-Key", f"{api_token}"),
    ]
    
    test_endpoints = [
        f"{base_url}/api/workspaces/",
        f"{base_url}/api/workspaces/{workspace_slug}/",
    ]
    
    async with aiohttp.ClientSession() as session:
        for endpoint in test_endpoints:
            print(f"🔄 Тестируем endpoint: {endpoint}")
            print("=" * 60)
            
            for auth_header, auth_value in auth_methods:
                headers = {
                    auth_header: auth_value,
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                }
                
                try:
                    print(f"   🔑 {auth_header}: {auth_value[:20]}...")
                    
                    async with session.get(endpoint, headers=headers) as response:
                        status = response.status
                        
                        if status == 200:
                            try:
                                data = await response.json()
                                print(f"   ✅ {status} - SUCCESS!")
                                if isinstance(data, dict):
                                    print(f"      📋 Keys: {list(data.keys())}")
                                elif isinstance(data, list):
                                    print(f"      📋 List with {len(data)} items")
                                    if data:
                                        print(f"      📋 First item keys: {list(data[0].keys()) if isinstance(data[0], dict) else 'Not dict'}")
                                break  # Найден рабочий метод
                            except Exception as parse_error:
                                text = await response.text()
                                print(f"   ✅ {status} - SUCCESS! (non-JSON response)")
                                print(f"      📋 Response: {text[:100]}...")
                        elif status == 401:
                            print(f"   🔑 {status} - Unauthorized")
                        elif status == 403:
                            print(f"   🚫 {status} - Forbidden")  
                        elif status == 404:
                            print(f"   ❌ {status} - Not Found")
                        else:
                            try:
                                text = await response.text()
                                print(f"   ⚠️ {status} - {text[:50]}...")
                            except:
                                print(f"   ⚠️ {status} - Unknown error")
                                
                except Exception as e:
                    print(f"   💥 Error: {str(e)}")
                    
            print()

if __name__ == "__main__":
    asyncio.run(test_plane_auth())