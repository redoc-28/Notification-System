import os
from pydantic import BaseSettings
from typing import Optional, Dict, Any
from functools import lru_cache


class Settings(BaseSettings):
    # API Settings
    API_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    PROJECT_NAME: str = "Notification Orchestrator Service"
    VERSION: str = "0.1.0"
    DESCRIPTION: str = "API for orchestrating notification delivery"

    # RabbitMQ Settings
    RABBITMQ_HOST: str = "localhost"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "guest"
    RABBITMQ_PASS: str = "guest"
    RABBITMQ_VHOST: str = "/"
    
    # RabbitMQ Exchange and Queue Names
    EXCHANGE_NAME: str = "notifications"
    EMAIL_QUEUE: str = "email_notifications"
    SMS_QUEUE: str = "sms_notifications"
    PUSH_QUEUE: str = "push_notifications"
    DLX_EXCHANGE: str = "notifications.dlx"  # Dead Letter Exchange
    
    # Redis Settings
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    
    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT: int = 10  # default requests per minute
    RATE_LIMIT_USER_MAP: Dict[str, int] = {}  # user_id: rate_limit
    
    # Deduplication
    DEDUPLICATION_ENABLED: bool = True
    DEDUPLICATION_TTL: int = 3600  # seconds
    
    # Retry Configuration
    MAX_RETRIES: int = 3
    RETRY_DELAY: int = 60  # seconds
    RETRY_BACKOFF_FACTOR: float = 2.0  # Exponential backoff
    
    # API Keys for External Services (In production, use a secret manager)
    SENDGRID_API_KEY: Optional[str] = None
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    FCM_API_KEY: Optional[str] = None

    class Config:
        env_file = ".env"
        case_sensitive = True
        
    def get_amqp_url(self) -> str:
        """Generate AMQP URL from settings"""
        return f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASS}@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/{self.RABBITMQ_VHOST}"
    
    def get_redis_url(self) -> str:
        """Generate Redis URL from settings"""
        password_part = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else "@"
        return f"redis://{password_part}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings"""
    return Settings()