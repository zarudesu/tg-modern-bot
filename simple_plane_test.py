#!/usr/bin/env python3
"""
Простой тест подключения к Plane API
"""
import asyncio
import aiohttp
import os
from datetime import datetime

# Используем переменные окружения вместо хардкода
PLANE_API_TOKEN = os.getenv("PLANE_API_TOKEN", "")
PLANE_BASE_URL = os.getenv("PLANE_API_URL", "")
PLANE_WORKSPACE_SLUG = os.getenv("PLANE_WORKSPACE_SLUG", "")

if not all([PLANE_API_TOKEN, PLANE_BASE_URL, PLANE_WORKSPACE_SLUG]):
    print("❌ Отсутствуют переменные окружения PLANE_API_TOKEN, PLANE_API_URL, PLANE_WORKSPACE_SLUG")
    exit(1)


async def test_plane_api():
    """Тест подключения к Plane API"""
    headers = {
        "Authorization": f"Bearer {PLANE_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            # Тест 1: Получение профиля
            async with session.get(
                f"{PLANE_BASE_URL}/api/users/me/",
                headers=headers
            ) as response:
                if response.status == 200:
                    user_data = await response.json()
                    print(f"✅ Профиль получен: {user_data.get('email', 'N/A')}")
                else:
                    print(f"❌ Ошибка получения профиля: {response.status}")
                    return False
            
            # Тест 2: Получение workspace
            async with session.get(
                f"{PLANE_BASE_URL}/api/workspaces/{PLANE_WORKSPACE_SLUG}/",
                headers=headers
            ) as response:
                if response.status == 200:
                    workspace_data = await response.json()
                    print(f"✅ Workspace найден: {workspace_data.get('name', 'N/A')}")
                else:
                    print(f"❌ Ошибка получения workspace: {response.status}")
                    return False
            
            # Тест 3: Получение проектов
            async with session.get(
                f"{PLANE_BASE_URL}/api/workspaces/{PLANE_WORKSPACE_SLUG}/projects/",
                headers=headers
            ) as response:
                if response.status == 200:
                    projects_data = await response.json()
                    print(f"✅ Проекты получены: {len(projects_data.get('results', []))} шт.")
                    return True
                else:
                    print(f"❌ Ошибка получения проектов: {response.status}")
                    return False
                    
    except Exception as e:
        print(f"💥 Исключение: {e}")
        return False


async def main():
    print("🧪 Тестирование Plane API...")
    print(f"🌐 URL: {PLANE_BASE_URL}")
    print(f"🏢 Workspace: {PLANE_WORKSPACE_SLUG}")
    print(f"📅 Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 50)
    
    success = await test_plane_api()
    
    print("-" * 50)
    if success:
        print("🎉 Все тесты пройдены успешно!")
    else:
        print("❌ Тесты провалены!")
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
