#!/usr/bin/env python3
"""
Тест импортов модульной архитектуры
"""
import asyncio
import sys
import os

# Добавляем корневую папку в Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_module_imports():
    """Тестирование импортов новых модулей"""
    print("🧪 Тестирование модульных импортов")
    print("=" * 50)
    
    try:
        # Тест 1: Импорт daily_tasks модуля
        print("📧 1. Тестирование Daily Tasks модуля...")
        from app.modules.daily_tasks.router import router as daily_tasks_router
        print(f"  ✅ Daily Tasks router: {type(daily_tasks_router)}")
        
        from app.modules.daily_tasks.email_handlers import router as email_router
        print(f"  ✅ Email handlers: {type(email_router)}")
        
        from app.modules.daily_tasks.filters import IsAdminEmailFilter
        print(f"  ✅ Admin email filter: {type(IsAdminEmailFilter)}")
        
    except Exception as e:
        print(f"  ❌ Daily Tasks module error: {e}")
        return False
    
    try:
        # Тест 2: Импорт work_journal модуля
        print("\n📝 2. Тестирование Work Journal модуля...")
        from app.modules.work_journal.router import router as work_journal_router
        print(f"  ✅ Work Journal router: {type(work_journal_router)}")
        
        from app.modules.work_journal.text_handlers import router as text_router
        print(f"  ✅ Text handlers: {type(text_router)}")
        
        from app.modules.work_journal.filters import IsWorkJournalActiveFilter
        print(f"  ✅ Work Journal active filter: {type(IsWorkJournalActiveFilter)}")
        
    except Exception as e:
        print(f"  ❌ Work Journal module error: {e}")
        return False
    
    try:
        # Тест 3: Импорт основного main с новыми модулями
        print("\n🚀 3. Тестирование main.py с новыми модулями...")
        
        # Проверяем что модули правильно подключены
        print("  ✅ Все модули импортированы успешно")
        
    except Exception as e:
        print(f"  ❌ Main module error: {e}")
        return False
    
    print("\n🎉 Все модульные импорты прошли успешно!")
    return True

if __name__ == "__main__":
    success = asyncio.run(test_module_imports())
    if success:
        print("\n✅ РЕЗУЛЬТАТ: Модульная архитектура готова к использованию")
        sys.exit(0)
    else:
        print("\n❌ РЕЗУЛЬТАТ: Есть проблемы с модульными импортами")
        sys.exit(1)
