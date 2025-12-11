import asyncpg
import redis.asyncio as redis
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any
import json
import structlog

from .config import get_settings

logger = structlog.get_logger()
settings = get_settings()

# Global connection pools
_db_pool: Optional[asyncpg.Pool] = None
_redis_client: Optional[redis.Redis] = None


async def init_db_pool() -> asyncpg.Pool:
    """Initialize PostgreSQL connection pool with optimized settings."""
    global _db_pool
    if _db_pool is None:
        _db_pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=settings.database_pool_min,
            max_size=settings.database_pool_max,
            command_timeout=30,
            max_inactive_connection_lifetime=300,
        )
        logger.info("Database pool initialized", min=settings.database_pool_min, max=settings.database_pool_max)
    return _db_pool


async def get_db_pool() -> asyncpg.Pool:
    """Get the database connection pool."""
    if _db_pool is None:
        return await init_db_pool()
    return _db_pool


async def close_db_pool():
    """Close the database connection pool."""
    global _db_pool
    if _db_pool:
        await _db_pool.close()
        _db_pool = None
        logger.info("Database pool closed")


async def init_redis() -> Optional[redis.Redis]:
    """Initialize Redis client for caching and rate limiting."""
    global _redis_client
    
    if not settings.redis_url:
        logger.info("Redis not configured, running without cache")
        return None
    
    if _redis_client is None:
        try:
            _redis_client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await _redis_client.ping()
            logger.info("Redis client initialized")
        except Exception as e:
            logger.warning("Failed to connect to Redis, running without cache", error=str(e))
            return None
    return _redis_client


async def get_redis() -> Optional[redis.Redis]:
    """Get the Redis client. Returns None if not available."""
    if _redis_client is None:
        return await init_redis()
    return _redis_client


async def close_redis():
    """Close the Redis client."""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
        logger.info("Redis client closed")


class ChatMemory:
    """Efficient chat memory management with PostgreSQL and optional Redis caching."""
    
    def __init__(self, session_id: str, table_name: str = None, context_length: int = None):
        self.session_id = session_id
        self.table_name = table_name or settings.chat_history_table
        self.context_length = context_length or settings.context_window_length
    
    async def get_history(self) -> List[Dict[str, str]]:
        """Get chat history with optional Redis caching."""
        redis_client = await get_redis()
        cache_key = f"chat_history:{self.session_id}"
        
        # Try cache first if available
        if redis_client:
            try:
                cached = await redis_client.get(cache_key)
                if cached:
                    return json.loads(cached)
            except Exception:
                pass
        
        # Fetch from database
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT role, content 
                FROM {self.table_name} 
                WHERE session_id = $1 
                ORDER BY created_at DESC 
                LIMIT $2
                """,
                self.session_id,
                self.context_length * 2  # human + ai messages
            )
        
        history = [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]
        
        # Cache for 5 minutes if Redis available
        if redis_client:
            try:
                await redis_client.setex(cache_key, 300, json.dumps(history))
            except Exception:
                pass
        
        return history
    
    async def add_message(self, role: str, content: str):
        """Add a message to chat history."""
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO {self.table_name} (session_id, role, content, created_at)
                VALUES ($1, $2, $3, NOW())
                """,
                self.session_id,
                role,
                content
            )
        
        # Invalidate cache if Redis available
        redis_client = await get_redis()
        if redis_client:
            try:
                await redis_client.delete(f"chat_history:{self.session_id}")
            except Exception:
                pass
    
    async def add_interaction(self, user_message: str, ai_response: str):
        """Add both user and AI messages in a single transaction."""
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    f"""
                    INSERT INTO {self.table_name} (session_id, role, content, created_at)
                    VALUES ($1, 'human', $2, NOW()), ($1, 'ai', $3, NOW())
                    """,
                    self.session_id,
                    user_message,
                    ai_response
                )
        
        # Invalidate cache if Redis available
        redis_client = await get_redis()
        if redis_client:
            try:
                await redis_client.delete(f"chat_history:{self.session_id}")
            except Exception:
                pass


class LogsManager:
    """Efficient logging to PostgreSQL."""
    
    def __init__(self, table_name: str = None):
        self.table_name = table_name or settings.logs_table
    
    async def log_request(self, user_id: str, username: str, email: str):
        """Log a request - creates or updates user record."""
        pool = await get_db_pool()
        try:
            async with pool.acquire() as conn:
                # Try upsert first (requires PRIMARY KEY or UNIQUE constraint)
                try:
                    await conn.execute(
                        f"""
                        INSERT INTO {self.table_name} (userid, username, correo, peticiones)
                        VALUES ($1, $2, $3, 1)
                        ON CONFLICT (userid) DO UPDATE SET peticiones = {self.table_name}.peticiones + 1
                        """,
                        user_id,
                        username,
                        email
                    )
                except Exception:
                    # Fallback: check if exists, then insert or update
                    existing = await conn.fetchval(
                        f"SELECT peticiones FROM {self.table_name} WHERE userid = $1",
                        user_id
                    )
                    if existing is not None:
                        await conn.execute(
                            f"UPDATE {self.table_name} SET peticiones = peticiones + 1 WHERE userid = $1",
                            user_id
                        )
                    else:
                        await conn.execute(
                            f"INSERT INTO {self.table_name} (userid, username, correo, peticiones) VALUES ($1, $2, $3, 1)",
                            user_id,
                            username,
                            email
                        )
        except Exception as e:
            logger.warning("Failed to log request", error=str(e))


class RateLimiter:
    """Token bucket rate limiter using Redis (optional)."""
    
    def __init__(self, max_requests: int = None, window_seconds: int = None):
        self.max_requests = max_requests or settings.rate_limit_requests
        self.window_seconds = window_seconds or settings.rate_limit_window
    
    async def is_allowed(self, user_id: str) -> tuple[bool, int]:
        """Check if request is allowed. Returns (allowed, remaining)."""
        redis_client = await get_redis()
        
        # If Redis not available, allow all requests (no rate limiting)
        if not redis_client:
            return True, self.max_requests
        
        try:
            key = f"rate_limit:{user_id}"
            
            current = await redis_client.get(key)
            if current is None:
                await redis_client.setex(key, self.window_seconds, 1)
                return True, self.max_requests - 1
            
            current = int(current)
            if current >= self.max_requests:
                return False, 0
            
            await redis_client.incr(key)
            return True, self.max_requests - current - 1
        except Exception:
            # On Redis error, allow the request
            return True, self.max_requests
