#!/usr/bin/env python3
"""
Тест подключения к Plane API с новыми настройками
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.integrations.plane_api import plane_api
from app.utils.logger import bot_logger

async def test_plane_connection():
    """Тестирование подключения к Plane API"""
    print("🔄 Тестируем подключение к Plane API...")
    print(f"📍 URL: {plane_api.api_url}")
    print(f"🏢 Workspace: {plane_api.workspace_slug}")
    print(f"🔑 API Token: {plane_api.api_token[:10]}...")
    print(f"✅ Configured: {plane_api.configured}")
    print()
    
    if not plane_api.configured:
        print("❌ Plane API не настроен!")
        return
    
    # Тестируем подключение
    result = await plane_api.test_connection()
    
    if result['success']:
        print("✅ Подключение успешно!")
        print(f"🏢 Workspace Name: {result.get('workspace_name', 'N/A')}")
        print(f"🆔 Workspace ID: {result.get('workspace_id', 'N/A')}")
    else:
        print("❌ Ошибка подключения!")
        print(f"🔥 Error: {result.get('error', 'Unknown error')}")
    
    print()
    
    # Тестируем получение задач для админа
    print("🔄 Тестируем получение задач для admin...")
    admin_user_id = 28795547  # ID админа
    
    try:
        tasks = await plane_api.get_all_assigned_tasks_by_user_id(admin_user_id)
        print(f"📋 Найдено задач: {len(tasks)}")
        
        if tasks:
            print("\n📋 Первые 3 задачи:")
            for i, task in enumerate(tasks[:3], 1):
                print(f"{i}. {task.state_emoji} {task.name}")
                print(f"   📊 Status: {task.state_name}")
                print(f"   👤 Assignee: {task.assignee_name}")
                print(f"   🏢 Project: {task.project_name}")
                print()
        else:
            print("📭 Задач не найдено")
            
    except Exception as e:
        print(f"❌ Ошибка получения задач: {e}")

if __name__ == "__main__":
    asyncio.run(test_plane_connection())