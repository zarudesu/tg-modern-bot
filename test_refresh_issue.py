#!/usr/bin/env python3
"""
Test script to debug the refresh button issue
"""
import asyncio
import sys
import os

# Add the current directory to Python path so relative imports work
sys.path.insert(0, os.path.dirname(__file__))

from app.integrations.plane_api import plane_api
from app.services.daily_tasks_service import DailyTasksService
from app.config import settings
from app.utils.logger import bot_logger

async def test_refresh_issue():
    """Test the refresh functionality to debug the 0 tasks issue"""
    
    admin_id = 28795547  # The admin user ID from logs
    admin_email = "zarudesu@gmail.com"
    
    print(f"🔍 Testing refresh issue for admin {admin_id} with email {admin_email}")
    
    # Test 1: Direct Plane API call
    print(f"\n📡 Test 1: Direct plane_api.get_user_tasks call")
    try:
        tasks1 = await plane_api.get_user_tasks(admin_email)
        print(f"✅ Direct API call returned {len(tasks1) if tasks1 else 0} tasks")
        
        if tasks1:
            print(f"First task: {tasks1[0].name} - Project: {tasks1[0].project_name}")
    except Exception as e:
        print(f"❌ Direct API call failed: {e}")
    
    # Test 2: Via DailyTasksService (simulating what the callback does)
    print(f"\n🔧 Test 2: DailyTasksService.get_admin_tasks call")
    try:
        # Create a mock DailyTasksService
        from aiogram import Bot
        mock_bot = Bot(token=settings.telegram_token)
        service = DailyTasksService(mock_bot)
        
        # Set up admin settings manually
        service.admin_settings[admin_id] = {'plane_email': admin_email}
        
        tasks2 = await service.get_admin_tasks(admin_id)
        print(f"✅ DailyTasksService call returned {len(tasks2) if tasks2 else 0} tasks")
        
        if tasks2:
            print(f"First task: {tasks2[0].name} - Project: {tasks2[0].project_name}")
    except Exception as e:
        print(f"❌ DailyTasksService call failed: {e}")
    
    # Test 3: Check if plane_api is configured correctly
    print(f"\n⚙️ Test 3: Plane API configuration check")
    print(f"Configured: {plane_api.configured}")
    if plane_api.configured:
        print(f"API URL: {plane_api.api_url}")
        print(f"Workspace: {plane_api.workspace_slug}")
        print(f"Token set: {'Yes' if hasattr(plane_api, 'token') and plane_api.token else 'No'}")
        
        # Test connection
        try:
            connection_result = await plane_api.test_connection()
            print(f"Connection test: {connection_result}")
        except Exception as e:
            print(f"Connection test failed: {e}")
    
    print(f"\n🎯 Test completed!")

if __name__ == "__main__":
    asyncio.run(test_refresh_issue())