#!/usr/bin/env python3
"""
Тест получения задач (issues) из Plane API
"""
import asyncio
import aiohttp
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def test_plane_issues():
    """Тестирование получения задач из Plane"""
    base_url = "https://plane.hhivp.com"
    api_token = "plane_api_15504fe9f81f4a819a79ff8409135447"
    workspace_slug = "hhivp"
    
    headers = {
        'X-API-Key': api_token,
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    # Тестируем различные endpoints для получения задач
    issue_endpoints = [
        f"{base_url}/api/v1/workspaces/{workspace_slug}/issues/",
        f"{base_url}/api/v1/workspaces/{workspace_slug}/my-issues/",
        f"{base_url}/api/v1/workspaces/{workspace_slug}/issues/assigned/",
        f"{base_url}/api/v1/workspaces/{workspace_slug}/user-issues/",
    ]
    
    async with aiohttp.ClientSession() as session:
        print("🔍 Тестируем endpoints для получения задач...")
        print("=" * 60)
        
        for endpoint in issue_endpoints:
            try:
                print(f"🔄 {endpoint}")
                
                async with session.get(endpoint, headers=headers) as response:
                    status = response.status
                    
                    if status == 200:
                        data = await response.json()
                        print(f"   ✅ {status} - SUCCESS!")
                        
                        if isinstance(data, dict):
                            print(f"      📊 Response structure: {list(data.keys())}")
                            
                            # Ищем задачи в разных структурах ответа
                            issues = None
                            if 'results' in data:
                                issues = data['results']
                            elif 'issues' in data:
                                issues = data['issues']
                            elif isinstance(data.get('grouped_by'), dict):
                                # Если данные сгруппированы
                                all_groups = []
                                for group_key, group_data in data['grouped_by'].items():
                                    if isinstance(group_data, list):
                                        all_groups.extend(group_data)
                                issues = all_groups
                            
                            if issues and isinstance(issues, list):
                                print(f"      📋 Найдено задач: {len(issues)}")
                                
                                if issues:
                                    first_issue = issues[0]
                                    print(f"      🎯 Структура первой задачи:")
                                    for key in list(first_issue.keys())[:10]:
                                        value = first_issue[key]
                                        if isinstance(value, str):
                                            print(f"         {key}: {value[:50]}{'...' if len(str(value)) > 50 else ''}")
                                        else:
                                            print(f"         {key}: {type(value).__name__}")
                                    
                                    # Важные поля для задач
                                    if 'name' in first_issue:
                                        print(f"      📝 Пример задачи: {first_issue['name']}")
                                    if 'assignee_details' in first_issue:
                                        assignee = first_issue['assignee_details']
                                        if assignee:
                                            print(f"      👤 Исполнитель: {assignee.get('display_name', 'N/A')}")
                                    if 'state_detail' in first_issue:
                                        state = first_issue['state_detail']
                                        print(f"      🏷️  Статус: {state.get('name', 'N/A')}")
                            else:
                                print(f"      ⚠️  Задачи не найдены в ответе")
                                
                        elif isinstance(data, list):
                            print(f"      📋 Прямой список задач: {len(data)} items")
                            if data:
                                first_item = data[0]
                                print(f"      📝 Первая задача: {first_item.get('name', 'N/A')}")
                                
                    elif status == 401:
                        print(f"   🔑 {status} - Unauthorized")
                    elif status == 404:
                        print(f"   ❌ {status} - Not Found")
                    else:
                        text = await response.text()
                        print(f"   ⚠️ {status} - {text[:100]}...")
                        
            except Exception as e:
                print(f"   💥 Error: {str(e)}")
        
        print()
        print("🔍 Тестируем получение участников workspace...")
        
        members_endpoint = f"{base_url}/api/v1/workspaces/{workspace_slug}/members/"
        
        try:
            print(f"🔄 {members_endpoint}")
            
            async with session.get(members_endpoint, headers=headers) as response:
                status = response.status
                
                if status == 200:
                    data = await response.json()
                    print(f"   ✅ {status} - SUCCESS!")
                    
                    if isinstance(data, list):
                        print(f"      👥 Найдено участников: {len(data)}")
                        
                        for i, member in enumerate(data[:3], 1):  # Первые 3
                            member_info = member.get('member', {})
                            email = member_info.get('email', 'N/A')
                            name = member_info.get('display_name', member_info.get('first_name', 'N/A'))
                            print(f"      {i}. 👤 {name} ({email})")
                    else:
                        print(f"      📊 Response structure: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                        
                else:
                    print(f"   ❌ {status}")
                    
        except Exception as e:
            print(f"   💥 Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_plane_issues())