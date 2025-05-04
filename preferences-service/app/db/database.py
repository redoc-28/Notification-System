import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, String, DateTime, Boolean, JSON, Text

from app.core.config import get_settings
from app.models.preferences import UserPreferences

logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

# Create SQLAlchemy engine
engine = create_async_engine(
    settings.get_db_url(),
    echo=settings.DEBUG,
    future=True
)

# Create async session factory
async_session = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Create base class for SQLAlchemy models
Base = declarative_base()


# Define models
class UserPreferencesModel(Base):
    """Model for storing user notification preferences"""
    __tablename__ = "user_preferences"
    
    user_id = Column(String, primary_key=True)
    channels = Column(JSON, nullable=False)
    categories = Column(JSON, nullable=False)
    do_not_disturb = Column(Boolean, nullable=False, default=False)
    timezone = Column(String, nullable=False, default="UTC")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


async def init_db():
    """Initialize database - create tables if they don't exist"""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise


class DatabaseClient:
    """Database client for interacting with PostgreSQL"""
    
    async def get_user_preferences(self, user_id: str) -> Optional[UserPreferences]:
        """
        Get user notification preferences
        
        Args:
            user_id: User ID
            
        Returns:
            UserPreferences: User's notification preferences or None if not found
        """
        try:
            async with async_session() as session:
                # Query for user preferences
                query = sa.select(UserPreferencesModel).where(UserPreferencesModel.user_id == user_id)
                result = await session.execute(query)
                user_prefs_model = result.scalar_one_or_none()
                
                if not user_prefs_model:
                    logger.info(f"User preferences not found for user: {user_id}")
                    return None
                
                # Convert to Pydantic model
                user_prefs = UserPreferences(
                    user_id=user_prefs_model.user_id,
                    channels=user_prefs_model.channels,
                    categories=user_prefs_model.categories,
                    do_not_disturb=user_prefs_model.do_not_disturb,
                    timezone=user_prefs_model.timezone,
                    created_at=user_prefs_model.created_at,
                    updated_at=user_prefs_model.updated_at
                )
                
                return user_prefs
                
        except Exception as e:
            logger.error(f"Error getting user preferences: {str(e)}")
            return None
            
    async def create_user_preferences(self, preferences: UserPreferences) -> bool:
        """
        Create user notification preferences
        
        Args:
            preferences: UserPreferences model
            
        Returns:
            bool: Success status
        """
        try:
            async with async_session() as session:
                # Convert Pydantic model to DB model
                user_prefs_model = UserPreferencesModel(
                    user_id=preferences.user_id,
                    channels=preferences.channels,
                    categories=preferences.categories,
                    do_not_disturb=preferences.do_not_disturb,
                    timezone=preferences.timezone
                )
                
                # Add to session
                session.add(user_prefs_model)
                
                # Commit the transaction
                await session.commit()
                
                logger.info(f"Created preferences for user: {preferences.user_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error creating user preferences: {str(e)}")
            return False
            
    async def update_user_preferences(self, preferences: UserPreferences) -> bool:
        """
        Update user notification preferences
        
        Args:
            preferences: UserPreferences model
            
        Returns:
            bool: Success status
        """
        try:
            async with async_session() as session:
                # Query for user preferences
                query = sa.select(UserPreferencesModel).where(UserPreferencesModel.user_id == preferences.user_id)
                result = await session.execute(query)
                user_prefs_model = result.scalar_one_or_none()
                
                if not user_prefs_model:
                    logger.warning(f"User preferences not found for update: {preferences.user_id}")
                    return False
                
                # Update fields
                user_prefs_model.channels = preferences.channels
                user_prefs_model.categories = preferences.categories
                user_prefs_model.do_not_disturb = preferences.do_not_disturb
                user_prefs_model.timezone = preferences.timezone
                user_prefs_model.updated_at = datetime.utcnow()
                
                # Commit the transaction
                await session.commit()
                
                logger.info(f"Updated preferences for user: {preferences.user_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating user preferences: {str(e)}")
            return False
            
    async def delete_user_preferences(self, user_id: str) -> bool:
        """
        Delete user notification preferences
        
        Args:
            user_id: User ID
            
        Returns:
            bool: Success status
        """
        try:
            async with async_session() as session:
                # Query for user preferences
                query = sa.delete(UserPreferencesModel).where(UserPreferencesModel.user_id == user_id)
                await session.execute(query)
                
                # Commit the transaction
                await session.commit()
                
                logger.info(f"Deleted preferences for user: {user_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error deleting user preferences: {str(e)}")
            return False


# Singleton instance
db_client = DatabaseClient()