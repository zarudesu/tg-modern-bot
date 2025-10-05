#!/usr/bin/env python3
"""
Простой тест исправления команды /plane_test
"""
import sys
import os

# Добавляем путь к проекту
sys.path.append('/Users/zardes/Projects/tg-mordern-bot')

def test_handlers():
    """Проверка обработчиков"""
    print("🧪 Тестирование исправлений обработчиков...")
    
    try:
        # Читаем файлы и проверяем содержимое
        with open('/Users/zardes/Projects/tg-mordern-bot/app/handlers/start.py', 'r') as f:
            start_content = f.read()
        
        with open('/Users/zardes/Projects/tg-mordern-bot/app/handlers/daily_tasks.py', 'r') as f:
            daily_content = f.read()
        
        # Проверяем что в start.py plane_test закомментирован
        start_plane_test_active = '@router.message(Command("plane_test"))' in start_content and not start_content.count('# @router.message(Command("plane_test"))')
        
        # Проверяем что в daily_tasks.py есть активный plane_test
        daily_plane_test_count = daily_content.count('@router.message(Command("plane_test"))')
        
        print(f"📋 Активных /plane_test в start.py: {1 if start_plane_test_active else 0}")
        print(f"📋 Активных /plane_test в daily_tasks.py: {daily_plane_test_count}")
        
        # Проверяем email handler
        email_handler_exists = 'F.text.regexp(r\'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$\')' in daily_content
        
        print(f"📧 Email handler найден: {'✅ да' if email_handler_exists else '❌ нет'}")
        
        # Результат
        if not start_plane_test_active and daily_plane_test_count >= 1 and email_handler_exists:
            print("\n✅ ВСЕ ИСПРАВЛЕНИЯ ПРИМЕНЕНЫ УСПЕШНО!")
            print("🤖 Теперь можете тестировать в боте:")
            print("   • /plane_test - должна работать новая полная версия")
            print("   • zarudesu@gmail.com - должно автоматически сохраниться")
            return True
        else:
            print("\n❌ Найдены проблемы в исправлениях")
            if start_plane_test_active:
                print("   • В start.py все еще активен plane_test")
            if daily_plane_test_count == 0:
                print("   • В daily_tasks.py нет активного plane_test")
            if not email_handler_exists:
                print("   • Email handler не найден")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        return False

def test_docker_status():
    """Проверка статуса Docker"""
    print("\n🐳 Проверка Docker...")
    
    result = os.system('cd /Users/zardes/Projects/tg-mordern-bot && docker-compose ps --quiet telegram-bot > /dev/null 2>&1')
    
    if result == 0:
        print("✅ Docker контейнер запущен")
        return True
    else:
        print("❌ Docker контейнер не запущен")
        print("🔧 Запустите: make dev-restart")
        return False

def main():
    """Основная функция"""
    print("🚀 Проверка исправлений /plane_test и email...")
    print("=" * 50)
    
    handlers_ok = test_handlers()
    docker_ok = test_docker_status()
    
    print("\n" + "=" * 50)
    print("📊 ИТОГОВЫЙ РЕЗУЛЬТАТ:")
    print("=" * 50)
    
    if handlers_ok and docker_ok:
        print("🎉 ВСЕ ГОТОВО К ТЕСТИРОВАНИЮ!")
        print("\n📱 Откройте Telegram и тестируйте:")
        print("   1. /plane_test - полная диагностика Plane API")
        print("   2. Отправьте: zarudesu@gmail.com")  
        print("   3. Должно появиться сообщение о сохранении email")
        print("\n💡 Если что-то не работает, проверьте логи:")
        print("   docker logs telegram-bot-app-full --follow")
    else:
        print("⚠️ Есть проблемы, требующие внимания")
        
    return handlers_ok and docker_ok

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
