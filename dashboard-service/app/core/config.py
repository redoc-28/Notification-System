import os
from pydantic_settings import BaseSettings  # Changed from 'from pydantic import BaseSettings'
from typing import Optional, Dict, Any
from functools import lru_cache


class Settings(BaseSettings):
    # API Settings
    API_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    PROJECT_NAME: str = "Notification Dashboard Service"
    VERSION: str = "0.1.0"
    DESCRIPTION: str = "API for monitoring notification delivery and analytics"
    
    # PostgreSQL Settings
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "notification_system"
    
    # Pagination Settings
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    
    # Security Settings (for production)
    SECRET_KEY: Optional[str] = None
    AUTH_ENABLED: bool = False
    AUTH_TOKEN_EXPIRY: int = 3600  # seconds

    class Config:
        env_file = ".env"
        case_sensitive = True
        
    def get_db_url(self) -> str:
        """Generate SQLAlchemy compatible PostgreSQL URL"""
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings"""
    return Settings()