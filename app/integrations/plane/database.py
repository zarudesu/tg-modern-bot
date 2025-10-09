"""
Plane PostgreSQL Database Direct Access Module
Bypasses rate-limited API by querying Plane's PostgreSQL database directly
"""
import asyncpg
from typing import List, Optional, Dict, Any
from ...utils.logger import bot_logger
from .models import PlaneTask, PlaneProject
from ...config import settings


class PlaneDatabaseClient:
    """
    Direct PostgreSQL access to Plane database (bypasses API rate limits)

    ВАЖНО: Подключается через SSH туннель к удалённому Docker контейнеру с Plane БД
    """

    def __init__(self):
        # SSH tunnel configuration (Plane DB runs in Docker on remote server)
        self.ssh_host = getattr(settings, 'plane_db_ssh_host', 'rd.hhivp.com')
        self.ssh_port = getattr(settings, 'plane_db_ssh_port', 22)

        # PostgreSQL in Docker container (accessible only via SSH tunnel)
        self.db_host = 'localhost'  # После создания SSH туннеля
        self.db_port = getattr(settings, 'plane_db_local_port', 15432)  # Локальный порт для туннеля
        self.db_name = 'plane'
        self.db_user = 'plane'
        self.db_password = 'plane'
        self.workspace_slug = settings.plane_workspace_slug
        self._pool: Optional[asyncpg.Pool] = None
        self._ssh_tunnel = None

    async def init_pool(self):
        """Initialize connection pool"""
        if self._pool is None:
            bot_logger.info(f"🔌 Initializing Plane DB connection pool: {self.db_host}:{self.db_port}/{self.db_name}")
            self._pool = await asyncpg.create_pool(
                host=self.db_host,
                port=self.db_port,
                user=self.db_user,
                password=self.db_password,
                database=self.db_name,
                min_size=2,
                max_size=10,
                command_timeout=30
            )
            bot_logger.info("✅ Plane DB pool initialized")

    async def close_pool(self):
        """Close connection pool"""
        if self._pool:
            await self._pool.close()
            self._pool = None
            bot_logger.info("🔌 Plane DB pool closed")

    async def get_user_tasks(self, user_email: str) -> List[PlaneTask]:
        """
        Get all tasks assigned to user by email - SINGLE SQL QUERY!

        This bypasses the rate-limited API by querying PostgreSQL directly.
        Replaces 52+ API calls with 1 database query.
        """
        try:
            await self.init_pool()

            bot_logger.info(f"🔍 [DB QUERY] Fetching tasks for {user_email}")

            # Single SQL query that joins all necessary tables
            query = """
                SELECT
                    i.id,
                    i.name,
                    i.description,
                    i.priority,
                    i.sequence_id,
                    i.start_date,
                    i.target_date,
                    i.project_id,
                    i.state_id,
                    i.workspace_id,
                    i.created_at,
                    i.updated_at,
                    p.name as project_name,
                    p.identifier as project_identifier,
                    p.description as project_description,
                    s.name as state_name,
                    s.group as state_group,
                    s.color as state_color,
                    u.id as assignee_id,
                    u.email as assignee_email,
                    u.display_name as assignee_display_name,
                    u.first_name as assignee_first_name,
                    u.last_name as assignee_last_name
                FROM issues i
                INNER JOIN issue_assignees ia ON i.id = ia.issue_id AND ia.deleted_at IS NULL
                INNER JOIN users u ON ia.assignee_id = u.id
                INNER JOIN projects p ON i.project_id = p.id AND p.deleted_at IS NULL
                INNER JOIN states s ON i.state_id = s.id AND s.deleted_at IS NULL
                WHERE u.email = $1
                  AND i.deleted_at IS NULL
                  AND LOWER(s.name) NOT IN ('done', 'completed', 'cancelled', 'canceled')
                ORDER BY
                    CASE i.priority
                        WHEN 'urgent' THEN 0
                        WHEN 'high' THEN 1
                        WHEN 'medium' THEN 2
                        WHEN 'low' THEN 3
                        ELSE 4
                    END,
                    i.target_date NULLS LAST;
            """

            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query, user_email)

            bot_logger.info(f"📊 [DB QUERY] Retrieved {len(rows)} tasks from PostgreSQL")

            # Convert rows to PlaneTask objects
            tasks = []
            for row in rows:
                try:
                    # Prepare task data compatible with PlaneTask model
                    task_data = {
                        'id': str(row['id']),
                        'name': row['name'],
                        'description': row['description'] if row['description'] else {},
                        'priority': row['priority'] or 'none',
                        'sequence_id': row['sequence_id'],
                        'start_date': str(row['start_date']) if row['start_date'] else None,
                        'target_date': str(row['target_date']) if row['target_date'] else None,
                        'project_id': str(row['project_id']),
                        'state_id': str(row['state_id']),
                        'workspace_id': str(row['workspace_id']),
                        'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                        'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None,

                        # Project details (enriched from JOIN)
                        'project_name': row['project_name'],
                        'project_detail': {
                            'id': str(row['project_id']),
                            'name': row['project_name'],
                            'identifier': row['project_identifier'],
                            'description': row['project_description'] if row['project_description'] else ''
                        },

                        # State details (enriched from JOIN)
                        'state_name': row['state_name'],
                        'state_detail': {
                            'id': str(row['state_id']),
                            'name': row['state_name'],
                            'group': row['state_group'],
                            'color': row['state_color']
                        },

                        # Assignee details (enriched from JOIN)
                        'assignee_details': {
                            'id': str(row['assignee_id']),
                            'email': row['assignee_email'],
                            'display_name': row['assignee_display_name'],
                            'first_name': row['assignee_first_name'],
                            'last_name': row['assignee_last_name']
                        },
                        'assignees': [str(row['assignee_id'])],  # List of assignee IDs

                        # State as dict for compatibility with API response format
                        'state': {
                            'id': str(row['state_id']),
                            'name': row['state_name'],
                            'group': row['state_group'],
                            'color': row['state_color']
                        }
                    }

                    plane_task = PlaneTask(**task_data)
                    tasks.append(plane_task)

                except Exception as parse_error:
                    bot_logger.error(f"Failed to parse task {row.get('sequence_id', 'unknown')}: {parse_error}")
                    continue

            bot_logger.info(f"✅ [DB QUERY] Parsed {len(tasks)} PlaneTask objects")
            return tasks

        except asyncpg.PostgresError as e:
            bot_logger.error(f"❌ PostgreSQL error: {e}")
            return []
        except Exception as e:
            bot_logger.error(f"❌ Error getting tasks from Plane DB: {e}")
            return []


# Global instance
plane_db_client = PlaneDatabaseClient()
