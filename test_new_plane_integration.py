#!/usr/bin/env python3
"""
Тест новой интеграции Plane API с проектами
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.integrations.plane_api_new import plane_api_new
from app.utils.logger import bot_logger

async def test_new_plane_integration():
    """Тестирование новой интеграции Plane API"""
    print("🔄 Тестируем новую интеграцию Plane API...")
    print(f"📍 URL: {plane_api_new.api_url}")
    print(f"🏢 Workspace: {plane_api_new.workspace_slug}")
    print(f"✅ Configured: {plane_api_new.configured}")
    print()
    
    if not plane_api_new.configured:
        print("❌ Plane API не настроен!")
        return
    
    # 1. Тестируем подключение
    print("🔍 Шаг 1: Тестируем подключение...")
    result = await plane_api_new.test_connection()
    
    if result['success']:
        print("✅ Подключение успешно!")
        print(f"🏢 Workspace: {result.get('workspace', 'N/A')}")
        print(f"📊 Projects: {result.get('projects_count', 0)}")
        print(f"📡 API Version: {result.get('api_version', 'N/A')}")
    else:
        print("❌ Ошибка подключения!")
        print(f"🔥 Error: {result.get('error', 'Unknown error')}")
        return
    
    print()
    
    # 2. Тестируем получение задач для тестового email
    print("🔍 Шаг 2: Тестируем получение задач для тестового email...")
    test_email = "zarudesu@gmail.com"  # Замените на реальный email
    
    try:
        tasks = await plane_api_new.get_user_tasks(test_email)
        print(f"📋 Найдено задач для {test_email}: {len(tasks)}")
        
        if tasks:
            print(f"\n📋 Первые {min(5, len(tasks))} задач:")
            for i, task in enumerate(tasks[:5], 1):
                print(f"{i}. {task.state_emoji} {task.name}")
                print(f"   📊 Status: {task.state_name}")
                print(f"   👤 Assignee: {task.assignee_name}")
                print(f"   🏢 Project: {task.project_name}")
                print(f"   🔑 Priority: {task.priority_emoji} {task.priority}")
                if task.target_date:
                    print(f"   📅 Due: {task.target_date}")
                print()
        else:
            print("📭 Задач не найдено")
            print("💡 Возможные причины:")
            print("   - Email не найден среди исполнителей")
            print("   - Нет активных задач (все завершены)")
            print("   - Проблемы с доступом к проектам")
            
    except Exception as e:
        print(f"❌ Ошибка получения задач: {e}")
    
    print()
    
    # 3. Тестируем получение задач для админа (по telegram ID)
    print("🔍 Шаг 3: Тестируем получение задач для админа...")
    admin_user_id = 28795547  # ID админа
    
    try:
        tasks = await plane_api_new.get_all_assigned_tasks_by_user_id(admin_user_id)
        print(f"📋 Найдено задач для admin {admin_user_id}: {len(tasks)}")
        
        if tasks:
            print(f"\n📋 Задачи админа:")
            for i, task in enumerate(tasks[:3], 1):
                print(f"{i}. {task.state_emoji} {task.name}")
                print(f"   📊 Status: {task.state_name}")
                print(f"   🏢 Project: {task.project_name}")
                print()
        else:
            print("📭 Задач не найдено для админа")
            print("💡 Проверьте настройку email в базе данных")
            
    except Exception as e:
        print(f"❌ Ошибка получения задач админа: {e}")

if __name__ == "__main__":
    asyncio.run(test_new_plane_integration())