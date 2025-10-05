#!/usr/bin/env python3
"""
Тест изоляции модулей после рефакторинга
Проверяет что email обрабатывается в daily_tasks, а не в work_journal
"""
import asyncio
import sys
import os

# Добавляем корневую папку в Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_email_isolation():
    """Тестирование изоляции email обработки"""
    print("🧪 Тест изоляции модулей")
    print("=" * 50)
    
    # Симулируем админа с ID 28795547
    admin_id = 28795547
    test_email = "zarudesu@gmail.com"
    
    try:
        # Импортируем фильтры
        from app.modules.daily_tasks.filters import IsAdminEmailFilter
        from app.modules.work_journal.filters import IsWorkJournalActiveFilter
        from app.config import settings
        
        print(f"👤 Тестовый админ ID: {admin_id}")
        print(f"📧 Тестовый email: {test_email}")
        print(f"🔧 Админы в системе: {settings.admin_user_id_list}")
        
        # Проверяем что админ ID корректно настроен
        is_admin_configured = admin_id in settings.admin_user_id_list
        print(f"✅ Админ настроен: {is_admin_configured}")
        
        if not is_admin_configured:
            print("⚠️ Внимание: Тестовый админ не найден в настройках")
            print("   Добавьте в .env: ADMIN_USER_ID=28795547")
        
        print("\n📧 Тестирование email фильтров:")
        
        # Создаем мок-объект сообщения
        class MockUser:
            def __init__(self, user_id):
                self.id = user_id
        
        class MockMessage:
            def __init__(self, text, user_id):
                self.text = text
                self.from_user = MockUser(user_id)
        
        # Тестовые сообщения
        email_message = MockMessage(test_email, admin_id)
        text_message = MockMessage("обычный текст", admin_id)
        
        # Тест 1: Email фильтр для daily_tasks
        email_filter = IsAdminEmailFilter()
        should_handle_email = await email_filter(email_message)
        should_ignore_text = await email_filter(text_message)
        
        print(f"  📧 Email '{test_email}' → daily_tasks: {should_handle_email}")
        print(f"  📝 Текст 'обычный текст' → daily_tasks: {should_ignore_text}")
        
        # Тест 2: Work journal фильтр НЕ должен обрабатывать email
        # (поскольку у пользователя нет активного состояния work_journal)
        wj_filter = IsWorkJournalActiveFilter()
        wj_should_ignore_email = await wj_filter(email_message)
        wj_should_ignore_text = await wj_filter(text_message)
        
        print(f"  📧 Email '{test_email}' → work_journal: {wj_should_ignore_email}")
        print(f"  📝 Текст 'обычный текст' → work_journal: {wj_should_ignore_text}")
        
        # Анализ результатов
        print("\n🎯 Анализ изоляции:")
        
        if should_handle_email and not wj_should_ignore_email:
            print("  ✅ Email корректно обрабатывается ТОЛЬКО в daily_tasks")
        elif should_handle_email and wj_should_ignore_email:
            print("  ⚠️  Email обрабатывается в ОБОИХ модулях - возможен конфликт!")
        elif not should_handle_email:
            print("  ❌ Email НЕ обрабатывается в daily_tasks - проблема фильтра!")
        
        if not should_ignore_text and not wj_should_ignore_text:
            print("  ✅ Обычный текст игнорируется ОБОИМИ модулями (без активных состояний)")
        
        print("\n🔍 Рекомендации:")
        print("  📧 Email должен обрабатываться ТОЛЬКО в daily_tasks")
        print("  📝 Work_journal должен работать ТОЛЬКО при активных состояниях")
        print("  🎯 Приоритет: daily_tasks > work_journal")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_email_isolation())
    if success:
        print("\n✅ РЕЗУЛЬТАТ: Тест изоляции модулей завершен")
    else:
        print("\n❌ РЕЗУЛЬТАТ: Ошибка в тестировании изоляции")
    sys.exit(0 if success else 1)
