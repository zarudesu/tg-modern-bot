#!/usr/bin/env python3
"""
Тест конфигурации Plane API для проверки подключения
"""

import sys
sys.path.append('.')

def test_plane_api_config():
    """Проверяем конфигурацию Plane API"""
    print("🛫 ТЕСТ КОНФИГУРАЦИИ PLANE API")
    print("=" * 50)
    
    try:
        from app.config import settings
        from app.integrations.plane_api import plane_api
        
        print("📊 Настройки Plane API:")
        print(f"   PLANE_BASE_URL: {getattr(settings, 'plane_base_url', 'НЕ УСТАНОВЛЕНО')}")
        print(f"   PLANE_API_TOKEN: {'УСТАНОВЛЕН' if getattr(settings, 'plane_api_token', None) else 'НЕ УСТАНОВЛЕНО'}")  
        print(f"   PLANE_WORKSPACE_SLUG: {getattr(settings, 'plane_workspace_slug', 'НЕ УСТАНОВЛЕНО')}")
        
        print(f"\n🔧 Состояние plane_api:")
        print(f"   configured: {plane_api.configured}")
        print(f"   base_url: {plane_api.base_url}")
        print(f"   workspace_slug: {plane_api.workspace_slug}")
        
        if plane_api.configured:
            print("✅ Plane API настроен корректно")
        else:
            print("❌ Plane API НЕ настроен - требуется конфигурация")
            print("\n🔧 Для настройки Plane API:")
            print("   1. Получите API токен от Plane")
            print("   2. Установите правильный BASE_URL") 
            print("   3. Укажите WORKSPACE_SLUG")
            
        return plane_api.configured
        
    except Exception as e:
        print(f"❌ Ошибка проверки конфигурации: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_plane_api_connection():
    """Тестируем подключение к Plane API"""
    print("\n🔗 ТЕСТ ПОДКЛЮЧЕНИЯ К PLANE API")
    print("=" * 50)
    
    try:
        from app.integrations.plane_api import plane_api
        
        if not plane_api.configured:
            print("❌ Plane API не настроен - пропускаем тест подключения")
            return False
            
        print("🔄 Тестируем подключение...")
        result = await plane_api.test_connection()
        
        if result.get('success'):
            print("✅ Подключение к Plane API успешно!")
            return True
        else:
            error = result.get('error', 'Неизвестная ошибка')
            print(f"❌ Ошибка подключения: {error}")
            return False
            
    except Exception as e:
        print(f"❌ Критическая ошибка тестирования: {e}")
        return False

def create_plane_api_demo_config():
    """Создаем демо конфигурацию для тестирования"""
    print("\n📝 СОЗДАНИЕ ДЕМО КОНФИГУРАЦИИ")
    print("=" * 50)
    
    demo_config = '''# ✈️ Plane API Integration (DEMO - замените на реальные значения)
PLANE_API_URL=https://demo-plane-instance.com  
PLANE_API_TOKEN=demo_token_replace_with_real
PLANE_WORKSPACE_SLUG=demo-workspace

# Для получения реальных данных:
# 1. Зарегистрируйтесь на https://plane.so
# 2. Создайте workspace 
# 3. Получите API токен в настройках
# 4. Замените значения выше
'''
    
    try:
        with open('.env.plane_demo', 'w') as f:
            f.write(demo_config)
        
        print("✅ Создан файл .env.plane_demo с демо конфигурацией")
        print("📋 Скопируйте нужные строки в ваш .env файл")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка создания демо конфигурации: {e}")
        return False

async def main():
    """Основная функция тестирования"""
    print("🎯 ПОЛНАЯ ПРОВЕРКА PLANE API")
    print("=" * 60)
    
    # Тест 1: Конфигурация
    config_ok = test_plane_api_config()
    
    # Тест 2: Подключение (если настроено)
    connection_ok = False
    if config_ok:
        connection_ok = await test_plane_api_connection()
    
    # Тест 3: Создание демо конфигурации
    demo_created = create_plane_api_demo_config()
    
    print("\n" + "=" * 60)
    print("📊 ИТОГИ ТЕСТИРОВАНИЯ:")
    print(f"   ✅ Конфигурация: {'ОК' if config_ok else 'ТРЕБУЕТ НАСТРОЙКИ'}")
    print(f"   ✅ Подключение: {'ОК' if connection_ok else 'НЕ ПРОТЕСТИРОВАНО'}")  
    print(f"   ✅ Демо создан: {'ОК' if demo_created else 'ОШИБКА'}")
    
    if not config_ok:
        print("\n⚠️ ТРЕБУЕТСЯ НАСТРОЙКА PLANE API")
        print("   Используйте файл .env.plane_demo как шаблон")
    elif config_ok and connection_ok:
        print("\n🎉 PLANE API ГОТОВ К РАБОТЕ!")
    elif config_ok and not connection_ok:
        print("\n⚠️ PLANE API НАСТРОЕН, НО ПОДКЛЮЧЕНИЕ НЕ РАБОТАЕТ")
        print("   Проверьте токен и доступность сервера")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())