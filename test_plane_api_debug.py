#!/usr/bin/env python3
"""
Скрипт для диагностики проблем с Plane API
"""
import asyncio
import aiohttp
import sys
import os
from datetime import datetime

# Add the current directory to Python path so relative imports work
sys.path.insert(0, os.path.dirname(__file__))

from app.config import settings

async def test_plane_api():
    """Тестируем Plane API напрямую"""
    
    # Конфигурация
    api_url = settings.plane_api_url  # https://plane.hhivp.com
    api_token = settings.plane_api_token  # plane_api_15504fe9f81f4a819a79ff8409135447
    workspace_slug = settings.plane_workspace_slug  # hhivp
    
    print(f"🔧 API URL: {api_url}")
    print(f"🔧 Workspace: {workspace_slug}")
    print(f"🔧 Token: {api_token[:20]}...")
    
    headers = {
        'X-API-Key': api_token,
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    async with aiohttp.ClientSession() as session:
        
        # Тест 1: Получить список проектов
        print(f"\n🔍 Test 1: Get projects")
        projects_url = f"{api_url}/api/v1/workspaces/{workspace_slug}/projects/"
        print(f"URL: {projects_url}")
        
        async with session.get(projects_url, headers=headers) as response:
            print(f"Status: {response.status}")
            if response.status == 200:
                projects_data = await response.json()
                print(f"Response type: {type(projects_data)}")
                print(f"Raw response (first 500 chars): {str(projects_data)[:500]}")
                
                # Пытаемся найти проекты в разных форматах
                projects = []
                if isinstance(projects_data, list):
                    projects = projects_data
                elif isinstance(projects_data, dict):
                    # Возможные ключи для проектов
                    for key in ['results', 'data', 'projects']:
                        if key in projects_data and isinstance(projects_data[key], list):
                            projects = projects_data[key]
                            print(f"✅ Found projects in '{key}': {len(projects)}")
                            break
                
                if projects:
                    first_project = projects[0]
                    print(f"First project: {first_project.get('name')} (ID: {first_project.get('id')})")
                    project_id = first_project.get('id')
                    
                    # Показываем все проекты
                    print(f"\n📋 All projects:")
                    for i, proj in enumerate(projects[:5]):  # Первые 5
                        print(f"  {i+1}. {proj.get('name', 'N/A')} (ID: {proj.get('id', 'N/A')})")
                else:
                    print("❌ No projects found")
                    return
            else:
                text = await response.text()
                print(f"❌ Error: {text}")
                return
        
        # Тест 2: Получить задачи первого проекта  
        print(f"\n🔍 Test 2: Get issues from first project")
        issues_url = f"{api_url}/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues/"
        print(f"URL: {issues_url}")
        
        async with session.get(issues_url, headers=headers) as response:
            print(f"Status: {response.status}")
            if response.status == 200:
                issues_data = await response.json()
                print(f"Response type: {type(issues_data)}")
                print(f"Response keys: {list(issues_data.keys()) if isinstance(issues_data, dict) else 'Not dict'}")
                
                # Извлекаем задачи
                issues = []
                if 'results' in issues_data:
                    issues = issues_data['results']
                    print(f"✅ Issues in 'results': {len(issues)}")
                elif isinstance(issues_data, list):
                    issues = issues_data
                    print(f"✅ Issues as list: {len(issues)}")
                else:
                    print(f"❓ Unexpected format: {issues_data}")
                
                # Анализируем первую задачу
                if issues:
                    first_issue = issues[0]
                    print(f"\n📋 First issue analysis:")
                    print(f"Name: {first_issue.get('name', 'N/A')}")
                    print(f"ID: {first_issue.get('id', 'N/A')}")
                    print(f"State: {first_issue.get('state_detail', {}).get('name', 'N/A')}")
                    print(f"Assignees field: {first_issue.get('assignees', 'N/A')}")
                    print(f"Assignee_details field: {first_issue.get('assignee_details', 'N/A')}")
                    
                    # Проверяем назначения
                    assigned_count = 0
                    for issue in issues[:10]:  # Первые 10
                        assignees = issue.get('assignees', [])
                        assignee_details = issue.get('assignee_details')
                        if assignees or assignee_details:
                            assigned_count += 1
                    
                    print(f"📊 Issues with assignees (first 10): {assigned_count}/10")
                else:
                    print("❌ No issues found")
            else:
                text = await response.text()
                print(f"❌ Error: {text}")
        
        # Тест 3: Проверим с expand параметром
        print(f"\n🔍 Test 3: Get issues with expand assignees")
        issues_expand_url = f"{api_url}/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues/?expand=assignees,state"
        print(f"URL: {issues_expand_url}")
        
        async with session.get(issues_expand_url, headers=headers) as response:
            print(f"Status: {response.status}")
            if response.status == 200:
                expanded_data = await response.json()
                print(f"Response type with expand: {type(expanded_data)}")
                
                # Извлекаем задачи
                issues = []
                if 'results' in expanded_data:
                    issues = expanded_data['results']
                elif isinstance(expanded_data, list):
                    issues = expanded_data
                
                if issues:
                    first_issue = issues[0]
                    print(f"First issue with expand - assignees: {first_issue.get('assignees', 'N/A')}")
                    print(f"First issue with expand - assignee_details: {first_issue.get('assignee_details', 'N/A')}")
            else:
                text = await response.text()
                print(f"❌ Expand error: {text}")
                
        # Тест 4: Получить участников проекта
        print(f"\n🔍 Test 4: Get project members")
        members_url = f"{api_url}/api/v1/workspaces/{workspace_slug}/projects/{project_id}/members/"
        print(f"URL: {members_url}")
        
        async with session.get(members_url, headers=headers) as response:
            print(f"Status: {response.status}")
            if response.status == 200:
                members_data = await response.json()
                print(f"Members type: {type(members_data)}")
                if isinstance(members_data, list):
                    print(f"✅ Members found: {len(members_data)}")
                    for member in members_data[:3]:  # Первые 3
                        user_data = member.get('member', {}) or member  
                        print(f"  - {user_data.get('email', 'N/A')} (ID: {user_data.get('id', 'N/A')})")
                else:
                    print(f"❓ Unexpected members format: {members_data}")
            else:
                text = await response.text()
                print(f"❌ Members error: {text}")

if __name__ == "__main__":
    asyncio.run(test_plane_api())