#!/usr/bin/env python3
"""
Тест функциональности ежедневных задач из Plane
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.integrations.plane_api import plane_api
from app.services.daily_tasks_service import DailyTasksService
from app.database.database import init_db


async def test_plane_connection():
    """Тест подключения к Plane API"""
    print("🔄 Тестирую подключение к Plane API...")
    
    if not plane_api.configured:
        print("❌ Plane API не настроен!")
        print("Проверьте настройки в .env:")
        print("- PLANE_API_URL")
        print("- PLANE_API_TOKEN") 
        print("- PLANE_WORKSPACE_SLUG")
        return False
    
    print(f"✅ Plane API настроен:")
    print(f"  URL: {plane_api.api_url}")
    print(f"  Workspace: {plane_api.workspace_slug}")
    print(f"  Token: {plane_api.api_token[:10]}...")
    
    return True


async def test_admin_settings():
    """Тест настроек админов"""
    print("\n📋 Тестирую настройки админов...")
    
    await init_db()
    
    # Создаем фиктивный бот для сервиса
    class FakeBot:
        async def send_message(self, **kwargs):
            print(f"📨 [ТЕСТ] Отправка сообщения в чат {kwargs['chat_id']}")
            print(f"📝 Сообщение: {kwargs['text'][:100]}...")
    
    daily_service = DailyTasksService(FakeBot())
    await daily_service._load_admin_settings_from_db()
    
    print(f"✅ Админов в системе: {len(settings.admin_user_id_list)}")
    
    for admin_id in settings.admin_user_id_list:
        admin_settings = await daily_service.get_admin_settings(admin_id)
        enabled = admin_settings.get('enabled', False)
        time_str = admin_settings.get('time', '09:00')
        timezone_str = admin_settings.get('timezone', 'Europe/Moscow')
        
        status = "✅ включены" if enabled else "❌ отключены"
        print(f"  👤 Admin {admin_id}: {status}, время {time_str} ({timezone_str})")
    
    return daily_service


async def test_get_tasks_for_admin(daily_service, admin_id):
    """Тест получения задач для админа"""
    print(f"\n🔍 Получаю задачи для админа {admin_id}...")
    
    try:
        tasks = await plane_api.get_all_assigned_tasks_by_user_id(admin_id)
        
        if not tasks:
            print("⚠️  Задачи не найдены. Возможные причины:")
            print("   • Не настроен email админа в БД")
            print("   • Нет назначенных задач в Plane")
            print("   • Все задачи завершены")
            return False
        
        print(f"✅ Найдено задач: {len(tasks)}")
        
        # Группируем задачи
        overdue = [t for t in tasks if t.is_overdue]
        today = [t for t in tasks if t.is_due_today and not t.is_overdue]
        upcoming = [t for t in tasks if not t.is_overdue and not t.is_due_today]
        
        print(f"  🔴 Просрочено: {len(overdue)}")
        print(f"  📅 На сегодня: {len(today)}")
        print(f"  📋 В работе: {len(upcoming)}")
        
        # Показываем несколько задач для примера
        if tasks:
            print("\n📝 Примеры задач:")
            for i, task in enumerate(tasks[:3]):
                print(f"  {i+1}. {task.priority_emoji} {task.state_emoji} {task.name[:50]}...")
                print(f"     📁 {task.project_name}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка получения задач: {e}")
        return False


async def test_send_daily_tasks(daily_service, admin_id):
    """Тест отправки ежедневных задач"""
    print(f"\n📨 Тестирую отправку задач админу {admin_id}...")
    
    try:
        success = await daily_service.send_daily_tasks_to_admin(admin_id, force=True)
        
        if success:
            print("✅ Тест отправки прошел успешно!")
            return True
        else:
            print("❌ Ошибка при тестовой отправке")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка тестовой отправки: {e}")
        return False


async def main():
    """Основная функция тестирования"""
    print("🧪 Тест функциональности ежедневных задач из Plane\n")
    
    # Тест 1: Подключение к Plane API
    if not await test_plane_connection():
        return
    
    # Тест 2: Настройки админов
    daily_service = await test_admin_settings()
    
    # Тест 3: Получение задач для каждого админа
    working_admins = []
    for admin_id in settings.admin_user_id_list:
        if await test_get_tasks_for_admin(daily_service, admin_id):
            working_admins.append(admin_id)
    
    if not working_admins:
        print("\n⚠️  Ни у одного админа не найдено задач.")
        print("Настройте email для админов через бота:")
        print("1. Отправьте /plane_test")
        print("2. Нажмите 'Настроить email'")
        print("3. Введите email из Plane")
        return
    
    # Тест 4: Отправка задач
    print(f"\n🧪 Тестирую отправку для {len(working_admins)} админов...")
    for admin_id in working_admins[:1]:  # Тестируем только для первого админа
        await test_send_daily_tasks(daily_service, admin_id)
    
    print("\n" + "="*50)
    print("✅ Тестирование завершено!")
    print("\nДля запуска ежедневных уведомлений:")
    print("1. Убедитесь что DAILY_TASKS_ENABLED=true в .env")
    print("2. Перезапустите бота: make dev-restart")
    print("3. Каждый админ настроит свое время через /daily_settings")


if __name__ == "__main__":
    asyncio.run(main())
