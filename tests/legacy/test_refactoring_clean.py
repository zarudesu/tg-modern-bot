#!/usr/bin/env python3
"""
ФИНАЛЬНЫЙ ТЕСТ РЕФАКТОРИНГА - МОДУЛЬНАЯ АРХИТЕКТУРА

Проверяет что рефакторинг выполнен успешно:
1. Старые handlers архивированы
2. Новые модули подключены в main.py  
3. Email изоляция работает (daily_tasks)
4. Work journal фильтры активности
"""
import asyncio
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_structure():
    """Тест структуры файлов"""
    print("📁 ТЕСТ СТРУКТУРЫ")
    print("-" * 30)
    
    base = Path(__file__).parent
    
    # Старые files должны быть в archive
    old_gone = not (base / "app/handlers/daily_tasks.py").exists()
    old_gone &= not (base / "app/handlers/work_journal.py").exists()
    
    # Новые модули должны существовать
    modules_exist = (base / "app/modules/daily_tasks/router.py").exists()
    modules_exist &= (base / "app/modules/work_journal/router.py").exists()
    
    print(f"  ✅ Старые handlers архивированы: {old_gone}")
    print(f"  ✅ Новые модули существуют: {modules_exist}")
    
    return old_gone and modules_exist

def test_main_imports():
    """Тест импортов в main.py"""
    print("\n🚀 ТЕСТ MAIN.PY")
    print("-" * 30)
    
    try:
        with open("app/main.py", "r") as f:
            content = f.read()
        
        # Новые импорты
        has_new = "from .modules.daily_tasks.router import" in content
        has_new &= "from .modules.work_journal.router import" in content
        
        # Нет старых импортов
        no_old = "from .handlers import daily_tasks" not in content
        no_old &= "from .handlers import work_journal" not in content
        
        print(f"  ✅ Новые модули импортированы: {has_new}")
        print(f"  ✅ Старые импорты удалены: {no_old}")
        
        return has_new and no_old
        
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        return False

async def test_isolation():
    """Тест изоляции модулей"""
    print("\n🔒 ТЕСТ ИЗОЛЯЦИИ")
    print("-" * 30)
    
    try:
        from app.modules.daily_tasks.filters import IsAdminEmailFilter
        from app.modules.work_journal.filters import IsWorkJournalActiveFilter
        
        # Мок объекты
        class MockUser:
            def __init__(self, user_id):
                self.id = user_id
        
        class MockMessage:
            def __init__(self, text, user_id):
                self.text = text
                self.from_user = MockUser(user_id)
        
        # Тестовые данные
        email_msg = MockMessage("zarudesu@gmail.com", 28795547)
        text_msg = MockMessage("обычный текст", 28795547)
        
        # Фильтры
        email_filter = IsAdminEmailFilter()
        wj_filter = IsWorkJournalActiveFilter()
        
        # Тесты
        email_to_daily = await email_filter(email_msg)
        text_to_daily = await email_filter(text_msg)
        email_to_wj = await wj_filter(email_msg)
        text_to_wj = await wj_filter(text_msg)
        
        print(f"  📧 Email → daily_tasks: {email_to_daily}")
        print(f"  📝 Text → daily_tasks: {text_to_daily}")
        print(f"  📧 Email → work_journal: {email_to_wj}")
        print(f"  📝 Text → work_journal: {text_to_wj}")
        
        # Правильная изоляция: email только в daily_tasks
        correct = email_to_daily and not text_to_daily and not email_to_wj and not text_to_wj
        
        print(f"  🎯 Изоляция правильная: {correct}")
        return correct
        
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        return False

async def main():
    """Главная функция"""
    print("🎯 ФИНАЛЬНЫЙ ТЕСТ РЕФАКТОРИНГА")
    print("=" * 40)
    
    tests = [
        test_structure(),
        test_main_imports(),
        await test_isolation()
    ]
    
    passed = sum(tests)
    total = len(tests)
    
    print(f"\n📊 РЕЗУЛЬТАТ: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 РЕФАКТОРИНГ УСПЕШЕН!")
        print("\n✅ Готово:")
        print("  📦 Модульная архитектура внедрена")
        print("  📧 Email изоляция работает")
        print("  📝 Work journal с фильтрами")
        print("  🔧 Main.py обновлен")
        
        print("\n🚀 Можно:")
        print("  • Добавлять новые модули в app/modules/")
        print("  • Разрабатывать новые фичи")
        print("  • Деплоить в продакшн")
        
        print("\n📚 Документация:")
        print("  • DEV_GUIDE_NEW.md - полное руководство")
        print("  • MODULAR_QUICK_REF.md - быстрая справка")
        
        return True
    else:
        print("\n⚠️ ЕСТЬ ПРОБЛЕМЫ - нужна доработка")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    print(f"\n{'✅ УСПЕХ' if success else '❌ НЕУДАЧА'}")
    sys.exit(0 if success else 1)
