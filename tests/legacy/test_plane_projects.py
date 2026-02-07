#!/usr/bin/env python3
"""
Тест получения проектов и задач через проекты из Plane API
"""
import asyncio
import aiohttp
import json
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def test_plane_projects():
    """Тестирование получения проектов и задач через проекты"""
    base_url = "https://plane.hhivp.com"
    api_token = "plane_api_15504fe9f81f4a819a79ff8409135447"
    workspace_slug = "hhivp"
    
    headers = {
        'X-API-Key': api_token,
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    async with aiohttp.ClientSession() as session:
        # 1. Получаем список проектов
        print("🔍 Шаг 1: Получаем список проектов...")
        projects_url = f"{base_url}/api/v1/workspaces/{workspace_slug}/projects/"
        
        try:
            async with session.get(projects_url, headers=headers) as response:
                if response.status == 200:
                    projects_data = await response.json()
                    print(f"✅ Проекты получены успешно!")
                    
                    # Анализируем структуру ответа
                    print(f"📊 Структура ответа: {list(projects_data.keys())}")
                    
                    # Ищем проекты в ответе
                    projects = None
                    if 'results' in projects_data:
                        projects = projects_data['results']
                    elif isinstance(projects_data, list):
                        projects = projects_data
                    elif 'grouped_by' in projects_data:
                        # Если проекты сгруппированы, соберем все
                        projects = []
                        for group in projects_data['grouped_by'].values():
                            if isinstance(group, list):
                                projects.extend(group)
                    
                    if projects:
                        print(f"📋 Найдено проектов: {len(projects)}")
                        
                        for i, project in enumerate(projects[:3], 1):  # Первые 3 проекта
                            project_id = project.get('id')
                            project_name = project.get('name', 'N/A')
                            print(f"   {i}. 🏢 {project_name} (ID: {project_id})")
                        
                        # 2. Получаем задачи для первого проекта
                        if projects:
                            first_project_id = projects[0].get('id')
                            print(f"\n🔍 Шаг 2: Получаем задачи для проекта {first_project_id}...")
                            
                            # Попробуем разные endpoints для задач проекта
                            issue_endpoints = [
                                f"{base_url}/api/v1/workspaces/{workspace_slug}/projects/{first_project_id}/issues/",
                                f"{base_url}/api/v1/workspaces/{workspace_slug}/projects/{first_project_id}/issues/list/",
                                f"{base_url}/api/v1/projects/{first_project_id}/issues/",
                            ]
                            
                            for endpoint in issue_endpoints:
                                try:
                                    print(f"   🔄 {endpoint}")
                                    
                                    async with session.get(endpoint, headers=headers) as issues_response:
                                        if issues_response.status == 200:
                                            issues_data = await issues_response.json()
                                            print(f"   ✅ SUCCESS! Задачи получены")
                                            
                                            # Анализируем задачи
                                            issues = None
                                            if 'results' in issues_data:
                                                issues = issues_data['results']
                                            elif isinstance(issues_data, list):
                                                issues = issues_data
                                            elif 'grouped_by' in issues_data:
                                                issues = []
                                                for group in issues_data['grouped_by'].values():
                                                    if isinstance(group, list):
                                                        issues.extend(group)
                                            
                                            if issues:
                                                print(f"      📋 Найдено задач: {len(issues)}")
                                                
                                                # Показываем первую задачу
                                                if issues:
                                                    first_issue = issues[0]
                                                    print(f"      📝 Первая задача:")
                                                    print(f"         Название: {first_issue.get('name', 'N/A')}")
                                                    print(f"         ID: {first_issue.get('id', 'N/A')}")
                                                    if 'assignee_details' in first_issue:
                                                        assignee = first_issue['assignee_details']
                                                        if assignee:
                                                            print(f"         Исполнитель: {assignee.get('display_name', 'N/A')}")
                                                    if 'state_detail' in first_issue:
                                                        state = first_issue['state_detail']
                                                        print(f"         Статус: {state.get('name', 'N/A')}")
                                            break  # Найден рабочий endpoint
                                            
                                        elif issues_response.status == 404:
                                            print(f"   ❌ 404 - Not Found")
                                        else:
                                            print(f"   ❌ {issues_response.status}")
                                            
                                except Exception as e:
                                    print(f"   💥 Error: {str(e)}")
                    else:
                        print("⚠️ Проекты не найдены в ответе")
                        print(f"Полный ответ: {json.dumps(projects_data, indent=2)[:500]}...")
                        
                else:
                    print(f"❌ Ошибка получения проектов: {response.status}")
                    
        except Exception as e:
            print(f"💥 Ошибка: {str(e)}")
        
        # 3. Пробуем получить участников через другие пути
        print(f"\n🔍 Шаг 3: Ищем участников через альтернативные пути...")
        
        member_endpoints = [
            f"{base_url}/api/v1/workspaces/{workspace_slug}/workspace-members/",
            f"{base_url}/api/v1/users/workspaces/{workspace_slug}/",
            f"{base_url}/api/v1/workspaces/{workspace_slug}/users/",
        ]
        
        for endpoint in member_endpoints:
            try:
                print(f"   🔄 {endpoint}")
                
                async with session.get(endpoint, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"   ✅ SUCCESS!")
                        
                        if isinstance(data, list):
                            print(f"      👥 Найдено участников: {len(data)}")
                            for i, member in enumerate(data[:2], 1):
                                member_info = member.get('member', member)
                                email = member_info.get('email', 'N/A')
                                name = member_info.get('display_name', member_info.get('first_name', 'N/A'))
                                print(f"         {i}. 👤 {name} ({email})")
                        else:
                            print(f"      📊 Структура: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                        break
                    else:
                        print(f"   ❌ {response.status}")
                        
            except Exception as e:
                print(f"   💥 Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_plane_projects())