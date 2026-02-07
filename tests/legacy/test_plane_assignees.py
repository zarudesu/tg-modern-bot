#!/usr/bin/env python3
"""
Анализ исполнителей в задачах Plane
"""
import asyncio
import aiohttp
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def analyze_plane_assignees():
    """Анализ всех исполнителей в задачах"""
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
        print("🔍 Получаем список проектов...")
        projects_url = f"{base_url}/api/v1/workspaces/{workspace_slug}/projects/"
        
        async with session.get(projects_url, headers=headers) as response:
            projects_data = await response.json()
            
            projects = []
            if 'results' in projects_data:
                projects = projects_data['results']
            
            print(f"📋 Найдено проектов: {len(projects)}")
            
            # 2. Анализируем исполнителей в первых 3 проектах
            all_assignees = set()
            
            for i, project in enumerate(projects[:3], 1):
                project_id = project.get('id')
                project_name = project.get('name')
                print(f"\n🏢 Проект {i}: {project_name}")
                
                # Получаем задачи проекта
                issues_url = f"{base_url}/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues/"
                
                async with session.get(issues_url, headers=headers) as issues_response:
                    if issues_response.status == 200:
                        issues_data = await issues_response.json()
                        
                        issues = []
                        if 'results' in issues_data:
                            issues = issues_data['results']
                        elif 'grouped_by' in issues_data:
                            for group in issues_data['grouped_by'].values():
                                if isinstance(group, list):
                                    issues.extend(group)
                        
                        print(f"   📋 Задач в проекте: {len(issues)}")
                        
                        project_assignees = set()
                        for issue in issues:
                            assignee_details = issue.get('assignee_details')
                            if assignee_details:
                                email = assignee_details.get('email', 'N/A')
                                name = assignee_details.get('display_name', 'N/A')
                                project_assignees.add(f"{name} ({email})")
                                all_assignees.add(f"{name} ({email})")
                        
                        if project_assignees:
                            print("   👥 Исполнители в проекте:")
                            for assignee in sorted(project_assignees):
                                print(f"      • {assignee}")
                        else:
                            print("   📭 Нет исполнителей в задачах")
            
            print(f"\n👥 Все уникальные исполнители найдены:")
            print("=" * 50)
            if all_assignees:
                for assignee in sorted(all_assignees):
                    print(f"• {assignee}")
            else:
                print("Исполнители не найдены")
                
            print(f"\n📊 Итого уникальных исполнителей: {len(all_assignees)}")

if __name__ == "__main__":
    asyncio.run(analyze_plane_assignees())