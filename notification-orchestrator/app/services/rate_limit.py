import logging
import time
from app.db.redis_client import redis_client
from app.core.config import get_settings
from app.models.notification import NotificationType

logger = logging.getLogger(__name__)


class RateLimitService:
    """
    Service for rate limiting notifications per user and channel
    """
    
    def __init__(self):
        self.settings = get_settings()
        
    async def check_rate_limit(self, user_id: str, notification_type: NotificationType) -> bool:
        """
        Check if user has exceeded rate limit for this notification type
        
        Args:
            user_id: User ID
            notification_type: Type of notification (email, sms, push)
            
        Returns:
            bool: True if rate limit is exceeded, False otherwise
        """
        if not self.settings.RATE_LIMIT_ENABLED:
            return False
            
        # Get rate limit for this user or use default
        rate_limit = self.settings.RATE_LIMIT_USER_MAP.get(
            user_id, 
            self.settings.RATE_LIMIT_DEFAULT
        )
        
        # Construct Redis key - track per user per notification type
        redis_key = f"rate_limit:{user_id}:{notification_type.value}:{int(time.time() // 60)}"
        
        # Get current count
        count = await redis_client.get(redis_key)
        count = int(count) if count else 0
        
        # Check if limit exceeded
        return count >= rate_limit
        
    async def increment_counter(self, user_id: str, notification_type: NotificationType) -> int:
        """
        Increment rate limit counter for user and notification type
        
        Args:
            user_id: User ID
            notification_type: Type of notification (email, sms, push)
            
        Returns:
            int: New counter value
        """
        if not self.settings.RATE_LIMIT_ENABLED:
            return 0
            
        # Current minute window
        current_minute = int(time.time() // 60)
        
        # Construct Redis key
        redis_key = f"rate_limit:{user_id}:{notification_type.value}:{current_minute}"
        
        # Increment counter and set expiry to 2 minutes
        count = await redis_client.incr(redis_key)
        await redis_client.set(redis_key, count, expire=120)  # Keep for current minute + next minute
        
        return count


# Singleton instance
rate_limit_service = RateLimitService()