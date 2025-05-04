import logging
from typing import Optional
from app.db.redis_client import redis_client
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class DeduplicationService:
    """
    Service for preventing duplicate notifications by using idempotency keys
    """
    
    def __init__(self):
        self.settings = get_settings()
        
    async def is_duplicate(self, idempotency_key: str) -> bool:
        """
        Check if a notification with this idempotency key was already processed
        
        Args:
            idempotency_key: Unique key for the notification
            
        Returns:
            bool: True if it's a duplicate, False otherwise
        """
        if not self.settings.DEDUPLICATION_ENABLED:
            return False
            
        # Construct Redis key
        redis_key = f"dedup:{idempotency_key}"
        
        # Check if key exists in Redis
        exists = await redis_client.exists(redis_key)
        
        return exists
        
    async def mark_as_processed(self, idempotency_key: str, notification_id: str) -> bool:
        """
        Mark a notification as processed to prevent duplicates
        
        Args:
            idempotency_key: Unique key for the notification
            notification_id: ID of the processed notification
            
        Returns:
            bool: Success status
        """
        if not self.settings.DEDUPLICATION_ENABLED:
            return True
            
        # Construct Redis key
        redis_key = f"dedup:{idempotency_key}"
        
        # Store in Redis with TTL
        return await redis_client.set(
            redis_key, 
            notification_id, 
            expire=self.settings.DEDUPLICATION_TTL
        )
        
    async def get_existing_notification_id(self, idempotency_key: str) -> Optional[str]:
        """
        Get the ID of an already processed notification with this idempotency key
        
        Args:
            idempotency_key: Unique key for the notification
            
        Returns:
            str: Notification ID if found, None otherwise
        """
        if not self.settings.DEDUPLICATION_ENABLED:
            return None
            
        # Construct Redis key
        redis_key = f"dedup:{idempotency_key}"
        
        # Get notification ID from Redis
        return await redis_client.get(redis_key)


# Singleton instance
deduplication_service = DeduplicationService()