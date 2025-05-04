import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, String, DateTime, Integer, JSON, Text, Boolean, Enum

from app.core.config import get_settings
from app.models.email import EmailStatus

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
class EmailDeliveryLogModel(Base):
    """Model for storing email delivery logs"""
    __tablename__ = "email_delivery_logs"
    
    id = Column(String, primary_key=True)
    notification_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    provider = Column(String, nullable=False)
    status = Column(Enum(EmailStatus), nullable=False, index=True)
    subject = Column(String, nullable=False)
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    provider_message_id = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    metadata = Column(JSON, nullable=True)
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
    
    async def log_email_delivery(self, 
                                log_id: str,
                                notification_id: str,
                                user_id: str,
                                provider: str,
                                status: EmailStatus,
                                subject: str,
                                sent_at: Optional[datetime] = None,
                                delivered_at: Optional[datetime] = None,
                                provider_message_id: Optional[str] = None,
                                error_message: Optional[str] = None,
                                retry_count: int = 0,
                                metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Log an email delivery attempt
        
        Args:
            log_id: Unique ID for this log entry
            notification_id: ID of the notification
            user_id: User ID
            provider: Email provider (sendgrid, smtp, ses)
            status: Delivery status
            subject: Email subject
            sent_at: When the email was sent
            delivered_at: When the email was delivered
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
                log_entry = EmailDeliveryLogModel(
                    id=log_id,
                    notification_id=notification_id,
                    user_id=user_id,
                    provider=provider,
                    status=status,
                    subject=subject,
                    sent_at=sent_at,
                    delivered_at=delivered_at,
                    provider_message_id=provider_message_id,
                    error_message=error_message,
                    retry_count=retry_count,
                    metadata=metadata
                )
                
                # Add to session
                session.add(log_entry)
                
                # Commit the transaction
                await session.commit()
                
                logger.info(f"Logged email delivery: {notification_id}, status: {status}")
                return True
                
        except Exception as e:
            logger.error(f"Error logging email delivery: {str(e)}")
            return False
            
    async def update_email_status(self,
                                log_id: str,
                                status: EmailStatus,
                                delivered_at: Optional[datetime] = None,
                                provider_message_id: Optional[str] = None,
                                error_message: Optional[str] = None) -> bool:
        """
        Update the status of an email delivery
        
        Args:
            log_id: Log entry ID
            status: New status
            delivered_at: When the email was delivered
            provider_message_id: Message ID from the provider
            error_message: Error message if failed
            
        Returns:
            bool: Success status
        """
        try:
            async with async_session() as session:
                # Get the log entry
                query = sa.select(EmailDeliveryLogModel).where(EmailDeliveryLogModel.id == log_id)
                result = await session.execute(query)
                log_entry = result.scalar_one_or_none()
                
                if not log_entry:
                    logger.warning(f"Email log entry not found: {log_id}")
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
                
                logger.info(f"Updated email status: {log_id}, new status: {status}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating email status: {str(e)}")
            return False


# Singleton instance
db_client = DatabaseClient()