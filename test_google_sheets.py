"""
Тест Google Sheets интеграции
"""
import asyncio
import sys
import os
import json
from pathlib import Path

# Добавляем путь к app модулю
sys.path.append(str(Path(__file__).parent / "app"))

from app.integrations.google_sheets import GoogleSheetsService, GoogleSheetsParser
from app.config import settings
from app.database.database import init_db
from app.utils.logger import bot_logger


async def test_google_sheets_connection():
    """Тест подключения к Google Sheets"""
    print("🔗 Тестирование подключения к Google Sheets...")
    
    try:
        parser = GoogleSheetsParser()
        
        # Инициализация
        print("📋 Инициализация Google Sheets клиента...")
        if await parser.initialize():
            print("✅ Google Sheets клиент инициализирован успешно")
        else:
            print("❌ Ошибка инициализации Google Sheets клиента")
            return False
        
        # Подключение к таблице
        print("📊 Подключение к таблице...")
        if await parser.connect_to_sheet():
            print("✅ Подключение к таблице успешно")
        else:
            print("❌ Ошибка подключения к таблице")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании подключения: {e}")
        return False


async def test_google_sheets_preview():
    """Тест получения превью данных"""
    print("\n📊 Тестирование получения превью данных...")
    
    try:
        service = GoogleSheetsService()
        
        # Получаем превью
        preview_data = await service.get_sheet_preview(limit=3)
        
        if preview_data:
            print(f"✅ Получено {len(preview_data)} записей")
            print("\n📋 Превью данных:")
            
            for i, entry in enumerate(preview_data, 1):
                print(f"\n{i}. Запись:")
                for key, value in entry.items():
                    # Ограничиваем длину значений для читаемости
                    display_value = str(value)[:50] + "..." if len(str(value)) > 50 else str(value)
                    print(f"   {key}: {display_value}")
            
            return True
        else:
            print("❌ Не удалось получить данные из таблицы")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка при получении превью: {e}")
        return False


async def test_google_sheets_sync():
    """Тест синхронизации данных"""
    print("\n🔄 Тестирование синхронизации данных...")
    
    try:
        # Инициализируем базу данных
        await init_db()
        print("✅ База данных инициализирована")
        
        service = GoogleSheetsService()
        
        # Синхронизируем данные
        sync_stats = await service.sync_from_sheets()
        
        print(f"\n📊 Результаты синхронизации:")
        print(f"   • Обработано записей: {sync_stats['total_processed']}")
        print(f"   • Добавлено новых: {sync_stats['new_entries']}")
        print(f"   • Пропущено (дубликаты): {sync_stats['skipped_entries']}")
        print(f"   • Ошибок: {sync_stats['error_entries']}")
        
        if sync_stats['error_entries'] == 0:
            print("✅ Синхронизация завершена успешно")
            return True
        else:
            print("⚠️ Синхронизация завершена с ошибками")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка при синхронизации: {e}")
        return False


async def test_configuration():
    """Тест конфигурации"""
    print("🔧 Проверка конфигурации...")
    
    config_ok = True
    
    # Проверяем Google Sheets ID
    if not settings.google_sheets_id:
        print("❌ GOOGLE_SHEETS_ID не настроен")
        config_ok = False
    else:
        print(f"✅ GOOGLE_SHEETS_ID: {settings.google_sheets_id}")
    
    # Проверяем credentials
    has_credentials = False
    
    if hasattr(settings, 'google_sheets_credentials_json') and settings.google_sheets_credentials_json:
        try:
            json.loads(settings.google_sheets_credentials_json)
            print("✅ GOOGLE_SHEETS_CREDENTIALS_JSON настроен и валиден")
            has_credentials = True
        except json.JSONDecodeError:
            print("❌ GOOGLE_SHEETS_CREDENTIALS_JSON неверного формата")
            config_ok = False
    
    if hasattr(settings, 'google_sheets_credentials_file') and settings.google_sheets_credentials_file:
        if os.path.exists(settings.google_sheets_credentials_file):
            print(f"✅ GOOGLE_SHEETS_CREDENTIALS_FILE найден: {settings.google_sheets_credentials_file}")
            has_credentials = True
        else:
            print(f"❌ GOOGLE_SHEETS_CREDENTIALS_FILE не найден: {settings.google_sheets_credentials_file}")
            config_ok = False
    
    if not has_credentials:
        print("❌ Не настроены Google Sheets credentials (ни JSON, ни файл)")
        config_ok = False
    
    return config_ok


async def main():
    """Основная функция тестирования"""
    print("🚀 Запуск тестирования Google Sheets интеграции")
    print("=" * 50)
    
    # 1. Проверка конфигурации
    if not await test_configuration():
        print("\n❌ Тестирование прервано из-за проблем с конфигурацией")
        print("\n📝 Для настройки:")
        print("1. Добавьте GOOGLE_SHEETS_ID в .env файл")
        print("2. Добавьте GOOGLE_SHEETS_CREDENTIALS_JSON или GOOGLE_SHEETS_CREDENTIALS_FILE")
        print("3. Убедитесь, что сервисный аккаунт имеет доступ к таблице")
        return
    
    # 2. Тест подключения
    if not await test_google_sheets_connection():
        print("\n❌ Тестирование прервано из-за проблем с подключением")
        return
    
    # 3. Тест превью данных
    if not await test_google_sheets_preview():
        print("\n❌ Не удалось получить данные из таблицы")
        return
    
    # 4. Тест синхронизации
    print("\n" + "=" * 50)
    choice = input("🤔 Запустить полную синхронизацию с базой данных? (y/N): ").lower()
    
    if choice in ['y', 'yes', 'да']:
        await test_google_sheets_sync()
    else:
        print("⏭️ Синхронизация пропущена")
    
    print("\n" + "=" * 50)
    print("✅ Тестирование завершено!")
    print("\n📋 Следующие шаги:")
    print("1. Используйте команду /sheets_sync в боте")
    print("2. Или используйте кнопку 'Синхронизация Google Sheets' в главном меню")
    print("3. Проверьте записи через команду /history")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Тестирование прервано пользователем")
    except Exception as e:
        print(f"\n💥 Критическая ошибка: {e}")
        sys.exit(1)
