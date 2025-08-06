#!/usr/bin/env python3
"""
Базовое тестирование бота без NetBox
"""
import asyncio
import sys
from pathlib import Path

# Добавляем app в Python path
sys.path.insert(0, str(Path(__file__).parent / "app"))

from app.config import settings
from app.database.database import init_db, close_db
from app.utils.logger import bot_logger


async def test_basic_config():
    """Тест базовой конфигурации"""
    print("🔧 Проверка базовой конфигурации...")
    
    required_vars = [
        "TELEGRAM_TOKEN",
        "ADMIN_USER_ID", 
        "DATABASE_URL"
    ]
    
    missing_vars = []
    
    for var in required_vars:
        value = getattr(settings, var.lower(), None)
        if not value:
            missing_vars.append(var)
        else:
            if "token" in var.lower():
                display_value = f"{str(value)[:10]}..."
            else:
                display_value = value
            print(f"  ✅ {var}: {display_value}")
    
    if missing_vars:
        print(f"❌ Отсутствуют переменные: {', '.join(missing_vars)}")
        return False
    
    print("✅ Базовая конфигурация в порядке")
    return True


async def test_database():
    """Тестирование подключения к базе данных"""
    print("\n🗄️ Тестирование базы данных...")
    
    try:
        await init_db()
        print("✅ База данных инициализирована успешно")
        
        await close_db()
        print("✅ Подключение к базе данных закрыто")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка базы данных: {e}")
        return False


async def main():
    """Основная функция"""
    print("🚀 Базовое тестирование бота")
    print("=" * 40)
    
    tests = [
        ("Базовая конфигурация", test_basic_config),
        ("База данных", test_database)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Тест '{test_name}' завершился с ошибкой: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 40)
    print("📊 Результаты:")
    
    passed = 0
    for test_name, result in results:
        status = "✅ ПРОШЕЛ" if result else "❌ ПРОВАЛЕН"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nИтого: {passed}/{len(results)} тестов прошло")
    
    if passed == len(results):
        print("\n🎉 Базовая конфигурация работает!")
        return True
    else:
        print("\n⚠️ Некоторые тесты провалены.")
        return False


if __name__ == "__main__":
    asyncio.run(main())
