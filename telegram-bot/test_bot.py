#!/usr/bin/env python3
"""
Скрипт для тестирования Telegram бота
"""
import asyncio
import os
import sys
from pathlib import Path

# Добавляем app в Python path
sys.path.insert(0, str(Path(__file__).parent / "app"))

from app.config import settings
from app.database.database import init_db, close_db
from app.services.netbox_service import NetBoxService
from app.utils.logger import bot_logger


async def test_database():
    """Тестирование подключения к базе данных"""
    print("🗄️ Тестирование базы данных...")
    
    try:
        await init_db()
        print("✅ База данных инициализирована успешно")
        
        await close_db()
        print("✅ Подключение к базе данных закрыто")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка базы данных: {e}")
        return False


async def test_netbox_api():
    """Тестирование NetBox API"""
    print("\n🔌 Тестирование NetBox API...")
    
    try:
        netbox = NetBoxService()
        
        # Тест получения устройств
        devices = await netbox.get_devices(limit=1)
        print(f"✅ NetBox API доступен, найдено устройств: {devices.get('count', 0)}")
        
        # Тест поиска
        search_results = await netbox.search_global("server")
        total_found = sum(len(items) for items in search_results.values())
        print(f"✅ Поиск работает, найдено результатов: {total_found}")
        
        # Тест получения сайтов
        sites = await netbox.get_sites(limit=5)
        print(f"✅ Получение сайтов работает, найдено: {sites.get('count', 0)}")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка NetBox API: {e}")
        return False


async def test_telegram_token():
    """Тестирование Telegram токена"""
    print("\n🤖 Тестирование Telegram токена...")
    
    try:
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            url = f"https://api.telegram.org/bot{settings.telegram_token}/getMe"
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    bot_info = data.get('result', {})
                    print(f"✅ Telegram токен валиден")
                    print(f"   Бот: @{bot_info.get('username', 'unknown')}")
                    print(f"   ID: {bot_info.get('id', 'unknown')}")
                    return True
                else:
                    print(f"❌ Неверный Telegram токен (статус: {response.status})")
                    return False
                    
    except Exception as e:
        print(f"❌ Ошибка проверки Telegram токена: {e}")
        return False


def test_environment():
    """Тестирование переменных окружения"""
    print("🔧 Проверка переменных окружения...")
    
    required_vars = [
        "TELEGRAM_TOKEN",
        "ADMIN_USER_ID", 
        "DATABASE_URL",
        "NETBOX_URL",
        "NETBOX_TOKEN"
    ]
    
    missing_vars = []
    
    for var in required_vars:
        value = getattr(settings, var.lower(), None)
        if not value:
            missing_vars.append(var)
        else:
            # Показываем только начало токенов для безопасности
            if "token" in var.lower():
                display_value = f"{str(value)[:10]}..."
            elif "url" in var.lower():
                display_value = value
            else:
                display_value = value
            print(f"  ✅ {var}: {display_value}")
    
    if missing_vars:
        print(f"❌ Отсутствуют переменные: {', '.join(missing_vars)}")
        return False
    
    print("✅ Все обязательные переменные окружения настроены")
    return True


def test_file_structure():
    """Проверка структуры файлов"""
    print("\n📁 Проверка структуры файлов...")
    
    required_files = [
        "app/main.py",
        "app/config.py",
        "app/database/models.py",
        "app/database/database.py",
        "app/services/netbox_service.py",
        "app/handlers/start.py",
        "app/handlers/search.py",
        "app/middleware/auth.py",
        "app/middleware/logging.py",
        "app/utils/logger.py",
        "app/utils/formatters.py",
        "requirements.txt",
        "Dockerfile",
        "docker-compose.yml",
        ".env"
    ]
    
    missing_files = []
    
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
        else:
            print(f"  ✅ {file_path}")
    
    if missing_files:
        print(f"❌ Отсутствуют файлы: {', '.join(missing_files)}")
        return False
    
    print("✅ Все необходимые файлы на месте")
    return True


async def run_all_tests():
    """Запуск всех тестов"""
    print("🚀 Запуск тестирования HHIVP Telegram Bot")
    print("=" * 50)
    
    tests = [
        ("Переменные окружения", test_environment),
        ("Структура файлов", test_file_structure),
        ("База данных", test_database),
        ("NetBox API", test_netbox_api),
        ("Telegram токен", test_telegram_token)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Тест '{test_name}' завершился с ошибкой: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("📊 Результаты тестирования:")
    
    passed = 0
    for test_name, result in results:
        status = "✅ ПРОШЕЛ" if result else "❌ ПРОВАЛЕН"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nИтого: {passed}/{len(results)} тестов прошло успешно")
    
    if passed == len(results):
        print("\n🎉 Все тесты прошли успешно! Бот готов к запуску.")
        return True
    else:
        print("\n⚠️ Некоторые тесты провалены. Исправьте ошибки перед запуском.")
        return False


async def main():
    """Основная функция"""
    try:
        success = await run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n🛑 Тестирование прервано пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Критическая ошибка тестирования: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
