import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import asyncpg
import redis.asyncio as redis
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from supabase import Client, create_client

from .config import settings

logger = logging.getLogger(__name__)

# SQLAlchemy setup
Base = declarative_base()
metadata = MetaData()

# Async engine for database operations
engine = create_async_engine(
    settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
    echo=settings.debug,
    pool_size=20,
    max_overflow=30,
    pool_timeout=30,
    pool_recycle=3600,
)

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Supabase client
supabase: Client = create_client(settings.supabase_url, settings.supabase_key)

# Redis client
redis_client = None


class DatabaseManager:
    """Database connection manager with connection pooling"""

    def __init__(self):
        self.pool = None
        self.redis_client = None

    async def init_db(self):
        """Initialize database connections"""
        try:
            # Initialize connection pool
            self.pool = await asyncpg.create_pool(
                settings.database_url,
                min_size=5,
                max_size=20,
                command_timeout=60,
                server_settings={
                    "jit": "off"  # Disable JIT for better performance on simple queries
                },
            )

            # Test the connection
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")

            logger.info("Database connection established successfully")

        except Exception as e:
            logger.warning(f"Database connection failed: {e}")
            logger.warning("Running in development mode without database")
            self.pool = None

        try:
            # Initialize Redis
            self.redis_client = redis.Redis.from_url(
                settings.redis_url, encoding="utf-8", decode_responses=True
            )

            await self.redis_client.ping()
            logger.info("Redis connection established successfully")

        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")
            logger.warning("Running without Redis caching")
            self.redis_client = None

    async def close_db(self):
        """Close database connections"""
        if self.pool:
            await self.pool.close()
        if self.redis_client:
            await self.redis_client.close()

    async def get_connection(self):
        """Get database connection from pool"""
        if not self.pool:
            raise Exception("Database not available - running in development mode")
        return self.pool.acquire()

    async def execute_query(self, query: str, *args):
        """Execute a read-only query safely"""
        if not self.pool:
            # Return mock data for development
            logger.warning("Database not available, returning mock data")
            return [
                {"total_patients": 42, "message": "Mock data - database not connected"}
            ]

        # Basic SQL injection prevention
        forbidden_keywords = [
            "DROP",
            "DELETE",
            "TRUNCATE",
            "ALTER",
            "CREATE",
            "INSERT",
            "UPDATE",
        ]
        query_upper = query.upper()

        for keyword in forbidden_keywords:
            if keyword in query_upper:
                raise ValueError(f"Query contains forbidden keyword: {keyword}")

        async with self.get_connection() as conn:
            try:
                return await conn.fetch(query, *args)
            except Exception as e:
                logger.error(f"Query execution failed: {e}")
                raise


# Global database manager instance
db_manager = DatabaseManager()


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_redis():
    """Get Redis client"""
    if not db_manager.redis_client:
        # Return a mock Redis client for development
        class MockRedis:
            async def get(self, key):
                return None

            async def set(self, key, value):
                return True

            async def setex(self, key, ttl, value):
                return True

            async def keys(self, pattern):
                return []

            async def ping(self):
                return True

        logger.warning("Redis not available, using mock client")
        return MockRedis()

    return db_manager.redis_client


# Schema registry for dynamic schema management
class SchemaRegistry:
    """Manages database schema information and caching"""

    def __init__(self):
        self.schema_cache = {}

    async def get_schema_info(self) -> dict:
        """Get current database schema information"""
        try:
            redis_client = await get_redis()

            # Try to get from cache first
            cached_schema = await redis_client.get("db_schema")
            if cached_schema:
                import json

                return json.loads(cached_schema)

            # Return mock data if database not available
            if not db_manager.pool:
                logger.warning("Database not available, returning mock schema")
                return {
                    "users": {"columns": [], "primary_keys": [], "foreign_keys": []}
                }

            # Query schema from database - FIXED LINE BELOW
            schema_query = """
            SELECT 
                t.table_name,
                c.column_name,
                c.data_type,
                c.is_nullable,
                c.column_default,
                kcu.constraint_name,
                tc.constraint_type
            FROM information_schema.tables t
            LEFT JOIN information_schema.columns c ON t.table_name = c.table_name
            LEFT JOIN information_schema.key_column_usage kcu ON c.table_name = kcu.table_name 
                AND c.column_name = kcu.column_name
            LEFT JOIN information_schema.table_constraints tc ON kcu.constraint_name = tc.constraint_name
            WHERE t.table_schema = 'public'
                AND t.table_type = 'BASE TABLE'
                AND c.table_schema = 'public'
            ORDER BY t.table_name, c.ordinal_position;
            """

            schema_data = {}
            async with db_manager.pool.acquire() as conn:
                rows = await conn.fetch(schema_query)

                for row in rows:
                    table_name = row["table_name"]
                    if table_name not in schema_data:
                        schema_data[table_name] = {
                            "columns": [],
                            "primary_keys": [],
                            "foreign_keys": [],
                        }

                    if row["column_name"]:
                        column_info = {
                            "name": row["column_name"],
                            "type": row["data_type"],
                            "nullable": row["is_nullable"] == "YES",
                            "default": row["column_default"],
                        }
                        schema_data[table_name]["columns"].append(column_info)

                        if row["constraint_type"] == "PRIMARY KEY":
                            schema_data[table_name]["primary_keys"].append(
                                row["column_name"]
                            )
                        elif row["constraint_type"] == "FOREIGN KEY":
                            schema_data[table_name]["foreign_keys"].append(
                                row["column_name"]
                            )

            await redis_client.setex(
                "db_schema", settings.schema_cache_ttl, json.dumps(schema_data)
            )

            return schema_data

        except Exception as e:
            logger.error(f"Failed to get schema info: {e}")
            # Return empty schema as fallback
            return {}


# Global schema registry
schema_registry = SchemaRegistry()
