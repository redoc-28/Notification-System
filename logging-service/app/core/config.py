import os
from pydantic import BaseSettings
from typing import Optional, Dict, Any
from functools import lru_cache


class Settings(BaseSettings):
    # Service Settings
    DEBUG: bool = False
    SERVICE_NAME: str = "Logging Service"
    VERSION: str = "0.1.0"
    
    # RabbitMQ Settings
    RABBITMQ_HOST: str = "localhost"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "guest"
    RABBITMQ_PASS: str = "guest"
    RABBITMQ_VHOST: str = "/"
    
    # RabbitMQ Queue Names
    EXCHANGE_NAME: str = "notifications"
    LOGGING_QUEUE: str = "notification_logs"
    SYSTEM_LOGS_QUEUE: str = "system_logs"
    DLX_EXCHANGE: str = "notifications.dlx"
    
    # PostgreSQL Settings
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "notification_system"
    
    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_RETENTION_DAYS: int = 30
    BATCH_SIZE: int = 100
    FLUSH_INTERVAL: int = 10  # seconds
    
    # Elasticsearch Settings (Optional)
    ELASTICSEARCH_ENABLED: bool = False
    ELASTICSEARCH_HOST: str = "localhost"
    ELASTICSEARCH_PORT: int = 9200
    ELASTICSEARCH_INDEX_PREFIX: str = "notification-logs"

    class Config:
        env_file = ".env"
        case_sensitive = True
        
    def get_amqp_url(self) -> str:
        """Generate AMQP URL from settings"""
        return f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASS}@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/{self.RABBITMQ_VHOST}"
    
    def get_db_url(self) -> str:
        """Generate SQLAlchemy compatible PostgreSQL URL"""
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings"""
    return Settings()