import asyncio
import asyncpg
from loguru import logger
from config import settings

async def init_db():
    """Инициализация базы данных"""
    
    try:
        # Подключение к базе данных
        conn = await asyncpg.connect(settings.DATABASE_URL)
        
        # Создание таблиц
        await create_tables(conn)
        
        logger.info("✅ База данных инициализирована")
        
        await conn.close()
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")
        raise

async def create_tables(conn):
    """Создание таблиц"""
    
    # Таблица пользователей
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id BIGINT PRIMARY KEY,
            username VARCHAR(255),
            first_name VARCHAR(255),
            last_name VARCHAR(255),
            is_admin BOOLEAN DEFAULT FALSE,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW(),
            last_activity TIMESTAMP DEFAULT NOW()
        )
    """)
    
    # Таблица поисковых запросов
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS search_queries (
            id SERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(id),
            query TEXT NOT NULL,
            query_type VARCHAR(50), -- search, ip, device, client, password
            results_found BOOLEAN DEFAULT FALSE,
            response_time_ms INTEGER,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    
    # Таблица логов доступа к паролям
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS password_access_logs (
            id SERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(id),
            service_name VARCHAR(255),
            access_type VARCHAR(50), -- search, view, copy
            ip_address INET,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    
    # Таблица статистики систем
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS system_stats (
            id SERIAL PRIMARY KEY,
            service_name VARCHAR(50), -- netbox, vaultwarden, bookstack
            metric_name VARCHAR(100),
            metric_value NUMERIC,
            recorded_at TIMESTAMP DEFAULT NOW()
        )
    """)
    
    # Таблица уведомлений
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id SERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(id),
            message TEXT,
            notification_type VARCHAR(50), -- info, warning, error, success
            is_read BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    
    logger.info("✅ Таблицы созданы")

async def get_db_connection():
    """Получение подключения к БД"""
    
    try:
        return await asyncpg.connect(settings.DATABASE_URL)
    except Exception as e:
        logger.error(f"Ошибка подключения к БД: {e}")
        raise

class UserRepository:
    """Репозиторий для работы с пользователями"""
    
    @staticmethod
    async def create_or_update_user(user_id: int, username: str = None, 
                                   first_name: str = None, last_name: str = None):
        """Создание или обновление пользователя"""
        
        conn = await get_db_connection()
        try:
            await conn.execute("""
                INSERT INTO users (id, username, first_name, last_name, last_activity)
                VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT (id) DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    last_activity = NOW()
            """, user_id, username, first_name, last_name)
            
        finally:
            await conn.close()
    
    @staticmethod
    async def get_user(user_id: int):
        """Получение пользователя"""
        
        conn = await get_db_connection()
        try:
            return await conn.fetchrow(
                "SELECT * FROM users WHERE id = $1", user_id
            )
        finally:
            await conn.close()
    
    @staticmethod
    async def is_admin(user_id: int) -> bool:
        """Проверка прав администратора"""
        
        conn = await get_db_connection()
        try:
            result = await conn.fetchval(
                "SELECT is_admin FROM users WHERE id = $1", user_id
            )
            return result or False
        finally:
            await conn.close()

class SearchRepository:
    """Репозиторий для поисковых запросов"""
    
    @staticmethod
    async def log_search(user_id: int, query: str, query_type: str, 
                        results_found: bool, response_time_ms: int = None):
        """Логирование поискового запроса"""
        
        conn = await get_db_connection()
        try:
            await conn.execute("""
                INSERT INTO search_queries (user_id, query, query_type, results_found, response_time_ms)
                VALUES ($1, $2, $3, $4, $5)
            """, user_id, query, query_type, results_found, response_time_ms)
            
        finally:
            await conn.close()
    
    @staticmethod
    async def get_user_search_stats(user_id: int, days: int = 7):
        """Статистика поисков пользователя"""
        
        conn = await get_db_connection()
        try:
            return await conn.fetch("""
                SELECT 
                    query_type,
                    COUNT(*) as count,
                    AVG(response_time_ms) as avg_response_time
                FROM search_queries 
                WHERE user_id = $1 AND created_at > NOW() - INTERVAL '%s days'
                GROUP BY query_type
                ORDER BY count DESC
            """ % days, user_id)
        finally:
            await conn.close()
    
    @staticmethod
    async def get_popular_queries(days: int = 7, limit: int = 10):
        """Популярные запросы"""
        
        conn = await get_db_connection()
        try:
            return await conn.fetch("""
                SELECT 
                    query,
                    COUNT(*) as count
                FROM search_queries 
                WHERE created_at > NOW() - INTERVAL '%s days'
                GROUP BY query
                ORDER BY count DESC
                LIMIT $1
            """ % days, limit)
        finally:
            await conn.close()

class PasswordAccessRepository:
    """Репозиторий для логов доступа к паролям"""
    
    @staticmethod
    async def log_password_access(user_id: int, service_name: str, 
                                 access_type: str, ip_address: str = None):
        """Логирование доступа к паролю"""
        
        conn = await get_db_connection()
        try:
            await conn.execute("""
                INSERT INTO password_access_logs (user_id, service_name, access_type, ip_address)
                VALUES ($1, $2, $3, $4)
            """, user_id, service_name, access_type, ip_address)
            
        finally:
            await conn.close()
    
    @staticmethod
    async def get_recent_password_access(days: int = 30, limit: int = 50):
        """Последние обращения к паролям"""
        
        conn = await get_db_connection()
        try:
            return await conn.fetch("""
                SELECT 
                    pal.*,
                    u.username,
                    u.first_name
                FROM password_access_logs pal
                JOIN users u ON pal.user_id = u.id
                WHERE pal.created_at > NOW() - INTERVAL '%s days'
                ORDER BY pal.created_at DESC
                LIMIT $1
            """ % days, limit)
        finally:
            await conn.close()
