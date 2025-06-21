import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, String, DateTime, Integer, JSON, Text, Boolean, Enum

from app.core.config import get_settings
from app.models.log import NotificationType, NotificationStatus, LogLevel

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
class NotificationLogModel(Base):
    """Model for storing notification logs"""
    __tablename__ = "notification_logs"
    
    id = Column(String, primary_key=True)
    notification_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    notification_type = Column(Enum(NotificationType), nullable=False, index=True)
    status = Column(Enum(NotificationStatus), nullable=False, index=True)
    provider = Column(String, nullable=False)
    subject = Column(String, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    provider_message_id = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    log_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class SystemLogModel(Base):
    """Model for storing system logs"""
    __tablename__ = "system_logs"
    
    id = Column(String, primary_key=True)
    service_name = Column(String, nullable=False, index=True)
    level = Column(Enum(LogLevel), nullable=False, index=True)
    message = Column(Text, nullable=False)
    correlation_id = Column(String, nullable=True, index=True)
    user_id = Column(String, nullable=True, index=True)
    log_metadata = Column(JSON, nullable=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class LogAggregationModel(Base):
    """Model for storing aggregated log statistics"""
    __tablename__ = "log_aggregations"
    
    id = Column(String, primary_key=True)
    date = Column(DateTime, nullable=False, index=True)
    notification_type = Column(Enum(NotificationType), nullable=False, index=True)
    status = Column(Enum(NotificationStatus), nullable=False, index=True)
    provider = Column(String, nullable=True, index=True)
    count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


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
    
    async def log_notification_event(self, log_data: Dict[str, Any]) -> bool:
        """
        Log a notification event
        
        Args:
            log_data: Dictionary containing log information
            
        Returns:
            bool: Success status
        """
        try:
            async with async_session() as session:
                # Create log entry
                log_entry = NotificationLogModel(
                    id=log_data.get('id') or str(uuid.uuid4()),
                    notification_id=log_data['notification_id'],
                    user_id=log_data['user_id'],
                    notification_type=log_data['notification_type'],
                    status=log_data['status'],
                    provider=log_data['provider'],
                    subject=log_data.get('subject'),
                    sent_at=log_data.get('sent_at'),
                    delivered_at=log_data.get('delivered_at'),
                    provider_message_id=log_data.get('provider_message_id'),
                    error_message=log_data.get('error_message'),
                    retry_count=log_data.get('retry_count', 0),
                    log_metadata=log_data.get('metadata'),
                    created_at=log_data.get('created_at', datetime.utcnow())
                )
                
                # Add to session
                session.add(log_entry)
                
                # Commit the transaction
                await session.commit()
                
                logger.debug(f"Logged notification event: {log_data['notification_id']}")
                return True
                
        except Exception as e:
            logger.error(f"Error logging notification event: {str(e)}")
            return False
            
    async def log_system_event(self, log_data: Dict[str, Any]) -> bool:
        """
        Log a system event
        
        Args:
            log_data: Dictionary containing log information
            
        Returns:
            bool: Success status
        """
        try:
            async with async_session() as session:
                # Create log entry
                log_entry = SystemLogModel(
                    id=log_data.get('id') or str(uuid.uuid4()),
                    service_name=log_data['service_name'],
                    level=log_data['level'],
                    message=log_data['message'],
                    correlation_id=log_data.get('correlation_id'),
                    user_id=log_data.get('user_id'),
                    log_metadata=log_data.get('metadata'),
                    timestamp=log_data.get('timestamp', datetime.utcnow())
                )
                
                # Add to session
                session.add(log_entry)
                
                # Commit the transaction
                await session.commit()
                
                logger.debug(f"Logged system event from {log_data['service_name']}")
                return True
                
        except Exception as e:
            logger.error(f"Error logging system event: {str(e)}")
            return False
            
    async def aggregate_logs(self, date: datetime) -> bool:
        """
        Aggregate logs for a specific date
        
        Args:
            date: Date to aggregate logs for
            
        Returns:
            bool: Success status
        """
        try:
            async with async_session() as session:
                # Get start and end of the day
                start_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = start_date + timedelta(days=1)
                
                # Query for aggregated data
                query = sa.text("""
                    SELECT 
                        notification_type,
                        status,
                        provider,
                        COUNT(*) as count
                    FROM notification_logs 
                    WHERE created_at >= :start_date AND created_at < :end_date
                    GROUP BY notification_type, status, provider
                """)
                
                result = await session.execute(query, {
                    'start_date': start_date,
                    'end_date': end_date
                })
                
                # Create aggregation entries
                for row in result:
                    aggregation = LogAggregationModel(
                        id=f"{start_date.date()}_{row.notification_type}_{row.status}_{row.provider}",
                        date=start_date,
                        notification_type=row.notification_type,
                        status=row.status,
                        provider=row.provider,
                        count=row.count
                    )
                    
                    # Use merge to handle duplicates
                    await session.merge(aggregation)
                
                # Commit the transaction
                await session.commit()
                
                logger.info(f"Aggregated logs for date: {date.date()}")
                return True
                
        except Exception as e:
            logger.error(f"Error aggregating logs: {str(e)}")
            return False
            
    async def cleanup_old_logs(self) -> bool:
        """
        Clean up old logs based on retention policy
        
        Returns:
            bool: Success status
        """
        try:
            async with async_session() as session:
                # Calculate cutoff date
                cutoff_date = datetime.utcnow() - timedelta(days=settings.LOG_RETENTION_DAYS)
                
                # Delete old notification logs
                notification_delete_query = sa.delete(NotificationLogModel).where(
                    NotificationLogModel.created_at < cutoff_date
                )
                notification_result = await session.execute(notification_delete_query)
                
                # Delete old system logs
                system_delete_query = sa.delete(SystemLogModel).where(
                    SystemLogModel.timestamp < cutoff_date
                )
                system_result = await session.execute(system_delete_query)
                
                # Commit the transaction
                await session.commit()
                
                logger.info(
                    f"Cleaned up {notification_result.rowcount} notification logs "
                    f"and {system_result.rowcount} system logs older than {cutoff_date}"
                )
                return True
                
        except Exception as e:
            logger.error(f"Error cleaning up old logs: {str(e)}")
            return False


# Singleton instance
db_client = DatabaseClient()