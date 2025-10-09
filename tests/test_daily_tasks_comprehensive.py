#!/usr/bin/env python3
"""
Полный тест daily_tasks модуля для проверки всех исправлений
"""

import sys
import asyncio
from datetime import time, datetime

sys.path.append('.')


async def test_daily_tasks_service():
    """Тест инициализации и работы DailyTasksService"""
    print("🧪 Тестируем DailyTasksService...")
    
    try:
        from app.services.daily_tasks_service import DailyTasksService, daily_tasks_service
        from app.integrations.plane_api import plane_api
        
        # Проверяем что глобальный сервис существует
        print(f"📋 Глобальный daily_tasks_service: {daily_tasks_service}")
        print(f"📋 Тип: {type(daily_tasks_service)}")
        
        if daily_tasks_service is None:
            print("❌ КРИТИЧЕСКАЯ ОШИБКА: daily_tasks_service = None")
            return False
        
        # Проверяем методы сервиса
        methods_to_check = ['get_admin_tasks', '_save_admin_settings_to_db', '_load_admin_settings_from_db']
        for method in methods_to_check:
            if hasattr(daily_tasks_service, method):
                print(f"✅ Метод {method} найден")
            else:
                print(f"❌ Метод {method} отсутствует")
                
        # Тестируем добавление настроек
        test_admin_id = 28795547
        test_email = "zarudesu@gmail.com"
        test_time = time(10, 0)
        
        print(f"🎯 Тестируем настройки для admin {test_admin_id}")
        
        # Добавляем настройки
        if test_admin_id not in daily_tasks_service.admin_settings:
            daily_tasks_service.admin_settings[test_admin_id] = {}
        
        daily_tasks_service.admin_settings[test_admin_id].update({
            'plane_email': test_email,
            'notification_time': test_time,
            'enabled': True
        })
        
        print(f"📊 Настройки после обновления: {daily_tasks_service.admin_settings}")
        
        # Тестируем plane_api
        print(f"🛫 Plane API configured: {plane_api.configured}")
        if plane_api.configured:
            print(f"🌐 Base URL: {plane_api.base_url}")
            print(f"🏢 Workspace: {plane_api.workspace_slug}")
        
        print("✅ DailyTasksService тест завершен")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования DailyTasksService: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_markdown_escaping():
    """Тест функции экранирования MarkdownV2"""
    print("🧪 Тестируем escape_markdown_v2...")
    
    try:
        from app.modules.daily_tasks.handlers import escape_markdown_v2
        
        test_cases = [
            ("test@example.com", "test\\\\@example\\\\.com"),
            ("user_name", "user\\\\_name"),
            ("Message with (brackets)", "Message with \\\\(brackets\\\\)"),
            ("Text with dots.txt", "Text with dots\\\\.txt"),
            ("Special chars: !@#$%^&*()", "Special chars: \\\\!\\\\@\\\\#\\$\\%\\^\\&\\\\*\\\\(\\\\)"),
            ("", "")
        ]
        
        all_passed = True
        for input_text, expected in test_cases:
            result = escape_markdown_v2(input_text)
            if result == expected:
                print(f"✅ '{input_text}' -> '{result}'")
            else:
                print(f"❌ '{input_text}' -> '{result}' (ожидали '{expected}')")
                all_passed = False
                
        if all_passed:
            print("✅ Все тесты escape_markdown_v2 пройдены")
            return True
        else:
            print("❌ Некоторые тесты escape_markdown_v2 провалены")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка тестирования escape_markdown_v2: {e}")
        return False


def test_module_imports():
    """Тест импортов всех модулей"""
    print("🧪 Тестируем импорты модулей daily_tasks...")
    
    modules_to_test = [
        ('app.modules.daily_tasks.handlers', 'router'),
        ('app.modules.daily_tasks.callback_handlers', 'router'), 
        ('app.modules.daily_tasks.email_handlers', 'router'),
        ('app.modules.daily_tasks.filters', 'IsAdminFilter')
    ]
    
    all_passed = True
    for module_name, attr_name in modules_to_test:
        try:
            module = __import__(module_name, fromlist=[attr_name])
            attr = getattr(module, attr_name)
            print(f"✅ {module_name} импортирован успешно")
        except Exception as e:
            print(f"❌ Ошибка импорта {module_name}: {e}")
            all_passed = False
            
    return all_passed


def test_time_conversion():
    """Тест конвертации времени"""
    print("🧪 Тестируем конвертацию времени...")
    
    try:
        from datetime import time as time_obj
        
        test_times = ["10:00", "09:30", "15:45", "23:59"]
        
        for time_str in test_times:
            try:
                hour, minute = map(int, time_str.split(':'))
                time_object = time_obj(hour, minute)
                print(f"✅ {time_str} -> {time_object}")
            except Exception as e:
                print(f"❌ Ошибка конвертации {time_str}: {e}")
                return False
                
        print("✅ Все тесты конвертации времени пройдены")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования конвертации времени: {e}")
        return False


async def main():
    """Основная функция тестирования"""
    print("🎯 ПОЛНЫЙ ТЕСТ DAILY_TASKS МОДУЛЯ")
    print("=" * 50)
    
    tests = [
        ("Импорты модулей", test_module_imports),
        ("MarkdownV2 экранирование", test_markdown_escaping),
        ("Конвертация времени", test_time_conversion),
        ("DailyTasksService", test_daily_tasks_service)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n🧪 Запуск теста: {test_name}")
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Критическая ошибка в тесте {test_name}: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
    
    passed = 0
    failed = 0
    for test_name, result in results:
        if result:
            print(f"✅ {test_name}")
            passed += 1
        else:
            print(f"❌ {test_name}")
            failed += 1
    
    print(f"\n🎯 Итого: {passed} пройдено, {failed} провалено")
    
    if failed == 0:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        return True
    else:
        print("⚠️ ЕСТЬ ПРОВАЛЕННЫЕ ТЕСТЫ - ТРЕБУЕТСЯ ИСПРАВЛЕНИЕ")
        return False


if __name__ == "__main__":
    asyncio.run(main())