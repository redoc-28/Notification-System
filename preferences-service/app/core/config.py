import os
from pydantic import BaseSettings
from typing import Optional, Dict, Any
from functools import lru_cache


class Settings(BaseSettings):
    # API Settings
    API_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    PROJECT_NAME: str = "Notification Preferences Service"
    VERSION: str = "0.1.0"
    DESCRIPTION: str = "API for managing user notification preferences"
    
    # PostgreSQL Settings
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "notification_system"
    
    # Caching Settings
    CACHE_ENABLED: bool = True
    CACHE_TTL: int = 300  # seconds
    
    # Default Preferences Settings
    DEFAULT_TIMEZONE: str = "UTC"
    DEFAULT_CHANNEL_ENABLED: bool = True
    DEFAULT_CATEGORY_ENABLED: bool = True
    DEFAULT_DO_NOT_DISTURB: bool = False
    
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