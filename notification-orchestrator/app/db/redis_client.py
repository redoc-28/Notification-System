import logging
from typing import Optional, Any
import redis.asyncio as redis
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class RedisClient:
    def __init__(self):
        self.settings = get_settings()
        self.redis_client = None
        
    async def connect(self):
        """Establish connection to Redis"""
        try:
            self.redis_client = redis.from_url(
                self.settings.get_redis_url(),
                encoding="utf-8",
                decode_responses=True
            )
            # Test connection
            await self.redis_client.ping()
            logger.info("Successfully connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            raise

    async def get(self, key: str) -> Optional[str]:
        """
        Get a value from Redis
        
        Args:
            key: Redis key
            
        Returns:
            Value or None if not found
        """
        if not self.redis_client:
            await self.connect()
            
        try:
            return await self.redis_client.get(key)
        except Exception as e:
            logger.error(f"Redis get error: {str(e)}")
            return None

    async def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """
        Set a value in Redis with optional expiry
        
        Args:
            key: Redis key
            value: Value to set
            expire: Expiry time in seconds (optional)
            
        Returns:
            bool: Success status
        """
        if not self.redis_client:
            await self.connect()
            
        try:
            return await self.redis_client.set(key, value, ex=expire)
        except Exception as e:
            logger.error(f"Redis set error: {str(e)}")
            return False

    async def delete(self, key: str) -> int:
        """
        Delete a key from Redis
        
        Args:
            key: Redis key
            
        Returns:
            int: Number of keys deleted
        """
        if not self.redis_client:
            await self.connect()
            
        try:
            return await self.redis_client.delete(key)
        except Exception as e:
            logger.error(f"Redis delete error: {str(e)}")
            return 0

    async def exists(self, key: str) -> bool:
        """
        Check if a key exists in Redis
        
        Args:
            key: Redis key
            
        Returns:
            bool: True if key exists
        """
        if not self.redis_client:
            await self.connect()
            
        try:
            return bool(await self.redis_client.exists(key))
        except Exception as e:
            logger.error(f"Redis exists error: {str(e)}")
            return False

    async def incr(self, key: str, amount: int = 1) -> int:
        """
        Increment a counter in Redis
        
        Args:
            key: Redis key
            amount: Amount to increment by
            
        Returns:
            int: New value
        """
        if not self.redis_client:
            await self.connect()
            
        try:
            return await self.redis_client.incrby(key, amount)
        except Exception as e:
            logger.error(f"Redis incr error: {str(e)}")
            return 0

    async def close(self):
        """Close the Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Redis connection closed")


# Singleton instance
redis_client = RedisClient()