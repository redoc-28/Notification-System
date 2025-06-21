import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, String, DateTime, Integer, JSON, Text, Boolean, Enum

from app.core.settings import get_settings
from app.models.push import PushStatus

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
class PushDeliveryLogModel(Base):
    """Model for storing push notification delivery logs"""
    __tablename__ = "push_delivery_logs"
    
    id = Column(String, primary_key=True)
    notification_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    provider = Column(String, nullable=False)
    status = Column(Enum(PushStatus), nullable=False, index=True)
    title = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    image_url = Column(String, nullable=True)
    action_url = Column(String, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    provider_message_id = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    notification_metadata = Column(JSON, nullable=True)
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
    
    async def log_push_delivery(self, 
                               log_id: str,
                               notification_id: str,
                               user_id: str,
                               provider: str,
                               status: PushStatus,
                               title: str,
                               body: str,
                               image_url: Optional[str] = None,
                               action_url: Optional[str] = None,
                               sent_at: Optional[datetime] = None,
                               delivered_at: Optional[datetime] = None,
                               provider_message_id: Optional[str] = None,
                               error_message: Optional[str] = None,
                               retry_count: int = 0,
                               metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Log a push notification delivery attempt
        
        Args:
            log_id: Unique ID for this log entry
            notification_id: ID of the notification
            user_id: User ID
            provider: Push provider (fcm, apn, webpush)
            status: Delivery status
            title: Push notification title
            body: Push notification body
            image_url: Optional image URL
            action_url: Optional action URL
            sent_at: When the push notification was sent
            delivered_at: When the push notification was delivered
            provider_message_id: Message ID from the provider
            error_message: Error message if failed
            retry_count: Number of retry attempts
            metadata: Additional metadata
            
        Returns:
            bool: Success status
        """
        try:
            async with async_session() as session:
                # Create log entry
                log_entry = PushDeliveryLogModel(
                    id=log_id,
                    notification_id=notification_id,
                    user_id=user_id,
                    provider=provider,
                    status=status,
                    title=title,
                    body=body,
                    image_url=image_url,
                    action_url=action_url,
                    sent_at=sent_at,
                    delivered_at=delivered_at,
                    provider_message_id=provider_message_id,
                    error_message=error_message,
                    retry_count=retry_count,
                    notification_metadata=metadata
                )
                
                # Add to session
                session.add(log_entry)
                
                # Commit the transaction
                await session.commit()
                
                logger.info(f"Logged push delivery: {notification_id}, status: {status}")
                return True
                
        except Exception as e:
            logger.error(f"Error logging push delivery: {str(e)}")
            return False
            
    async def update_push_status(self,
                               log_id: str,
                               status: PushStatus,
                               delivered_at: Optional[datetime] = None,
                               provider_message_id: Optional[str] = None,
                               error_message: Optional[str] = None) -> bool:
        """
        Update the status of a push notification delivery
        
        Args:
            log_id: Log entry ID
            status: New status
            delivered_at: When the push notification was delivered
            provider_message_id: Message ID from the provider
            error_message: Error message if failed
            
        Returns:
            bool: Success status
        """
        try:
            async with async_session() as session:
                # Get the log entry
                query = sa.select(PushDeliveryLogModel).where(PushDeliveryLogModel.id == log_id)
                result = await session.execute(query)
                log_entry = result.scalar_one_or_none()
                
                if not log_entry:
                    logger.warning(f"Push log entry not found: {log_id}")
                    return False
                
                # Update fields
                log_entry.status = status
                if delivered_at:
                    log_entry.delivered_at = delivered_at
                if provider_message_id:
                    log_entry.provider_message_id = provider_message_id
                if error_message:
                    log_entry.error_message = error_message
                log_entry.updated_at = datetime.utcnow()
                
                # Commit the transaction
                await session.commit()
                
                logger.info(f"Updated push status: {log_id}, new status: {status}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating push status: {str(e)}")
            return False


# Singleton instance
db_client = DatabaseClient()