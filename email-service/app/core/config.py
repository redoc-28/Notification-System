import os
from pydantic_settings import BaseSettings
from typing import Optional, Dict, Any
from functools import lru_cache


class Settings(BaseSettings):
    # Service Settings
    DEBUG: bool = False
    SERVICE_NAME: str = "Email Service"
    VERSION: str = "0.1.0"
    
    # RabbitMQ Settings
    RABBITMQ_HOST: str = "localhost"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "guest"
    RABBITMQ_PASS: str = "guest"
    RABBITMQ_VHOST: str = "/"
    
    # RabbitMQ Queue Names
    EXCHANGE_NAME: str = "notifications"
    EMAIL_QUEUE: str = "email_notifications"
    DLX_EXCHANGE: str = "notifications.dlx"  # Dead Letter Exchange
    DLQ_QUEUE: str = "email_notifications.dlq"  # Dead Letter Queue
    
    # PostgreSQL Settings
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "notification_system"
    
    # Email Provider Settings
    EMAIL_PROVIDER: str = "sendgrid"  # Options: sendgrid, smtp, ses
    DEFAULT_FROM_EMAIL: str = "noreply@example.com"
    DEFAULT_REPLY_TO: str = "support@example.com"
    
    # SendGrid Settings
    SENDGRID_API_KEY: Optional[str] = None
    
    # SMTP Settings
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_USE_TLS: bool = True
    
    # AWS SES Settings
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: Optional[str] = None
    
    # Retry Configuration
    MAX_RETRIES: int = 3
    RETRY_DELAY: int = 60  # seconds
    RETRY_BACKOFF_FACTOR: float = 2.0  # Exponential backoff

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