import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # API Settings
    API_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    
    # RabbitMQ Settings
    RABBITMQ_HOST: str = "rabbitmq"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "admin"
    RABBITMQ_PASS: str = "adminpass"
    EXCHANGE_NAME: str = "notifications"
    DLX_EXCHANGE: str = "notifications.dlx"
    PUSH_QUEUE: str = "push_notifications"
    DLQ_QUEUE: str = "push_notifications.dlq"
    
    # Database Settings
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "notification_system"
    
    # Push Notification Settings
    PUSH_PROVIDER: str = "fcm"  # Options: fcm, apn, webpush
    
    # FCM Settings
    FCM_SERVER_KEY: str = ""
    FCM_SERVICE_ACCOUNT_JSON: str = ""
    
    # APNs Settings
    APN_KEY_ID: str = ""
    APN_AUTH_KEY: str = ""
    APN_TEAM_ID: str = ""
    APN_BUNDLE_ID: str = ""
    
    # Retry Settings
    MAX_RETRIES: int = 3
    RETRY_DELAY: int = 5
    RETRY_BACKOFF_FACTOR: int = 2
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True
    )
    
    def get_amqp_url(self) -> str:
        """Get RabbitMQ connection URL"""
        return f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASS}@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/"
    
    def get_db_url(self) -> str:
        """Get PostgreSQL connection URL"""
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings() 