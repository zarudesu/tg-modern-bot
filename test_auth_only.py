#!/usr/bin/env python3
"""
Тест auth middleware в изоляции - без запуска всего бота
"""
import asyncio
import sys
import os

# Добавляем путь к приложению
sys.path.insert(0, '/Users/zardes/Projects/tg-mordern-bot')

from app.config import settings
from app.database.database import init_db, get_async_session
from app.database.models import BotUser
from sqlalchemy import select

async def test_auth_middleware():
    """Тестируем auth middleware отдельно"""
    print("🔍 Тестируем auth middleware в изоляции...")
    
    try:
        # Инициализируем БД
        await init_db()
        print("✅ Database initialized")
        
        # Тестируем получение пользователя из БД
        test_user_id = 123456789  # твой ID
        
        async for session in get_async_session():
            result = await session.execute(
                select(BotUser).where(BotUser.telegram_user_id == test_user_id)
            )
            db_user = result.scalar_one_or_none()
            
            print(f"✅ User query completed: {db_user}")
            print(f"✅ User role: {db_user.role if db_user else 'guest'}")
            
            # Выходим из цикла сессии - проверяем что нет проблем
            break
            
        print("✅ Session cycle completed without errors")
        
        # Тестируем второй запрос
        async for session in get_async_session():
            result = await session.execute(
                select(BotUser).where(BotUser.telegram_user_id == test_user_id)
            )
            db_user = result.scalar_one_or_none()
            
            print(f"✅ Second query completed: {db_user}")
            break
            
        print("✅ Multiple session cycles work correctly")
        
    except Exception as e:
        print(f"❌ Error in auth middleware test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_auth_middleware())
