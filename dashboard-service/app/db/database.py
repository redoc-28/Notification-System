import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, date, timedelta
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, String, DateTime, Integer, JSON, Text, Boolean, Enum, Date, func, text, select

from app.core.config import get_settings
from app.models.dashboard import (
    NotificationType, 
    NotificationStatus, 
    TimeRange,
    NotificationDeliveryLog,
    NotificationStats,
    DailyStats
)

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


# Define models for direct DB queries (these are not used for ORM operations)
# Instead, they define the structure of the existing tables created by other services
class EmailDeliveryLogModel(Base):
    """Model for email delivery logs (read-only)"""
    __tablename__ = "email_delivery_logs"
    
    id = Column(String, primary_key=True)
    notification_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    provider = Column(String, nullable=False)
    status = Column(String, nullable=False, index=True)
    subject = Column(String, nullable=False)
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    provider_message_id = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class SMSDeliveryLogModel(Base):
    """Model for SMS delivery logs (read-only)"""
    __tablename__ = "sms_delivery_logs"
    
    id = Column(String, primary_key=True)
    notification_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    provider = Column(String, nullable=False)
    status = Column(String, nullable=False, index=True)
    body = Column(Text, nullable=False)
    sender_id = Column(String, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    provider_message_id = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class PushDeliveryLogModel(Base):
    """Model for push notification delivery logs (read-only)"""
    __tablename__ = "push_delivery_logs"
    
    id = Column(String, primary_key=True)
    notification_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    provider = Column(String, nullable=False)
    status = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    image_url = Column(String, nullable=True)
    action_url = Column(String, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    provider_message_id = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class DailyStatsModel(Base):
    """Model for storing aggregated daily stats"""
    __tablename__ = "notification_daily_stats"
    
    date = Column(Date, primary_key=True)
    total = Column(Integer, nullable=False, default=0)
    email = Column(Integer, nullable=False, default=0)
    sms = Column(Integer, nullable=False, default=0)
    push = Column(Integer, nullable=False, default=0)
    sent = Column(Integer, nullable=False, default=0)
    delivered = Column(Integer, nullable=False, default=0)
    failed = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


async def init_db():
    """Initialize database - create tables if they don't exist"""
    try:
        async with engine.begin() as conn:
            # Only create our own tables - the delivery logs are managed by other services
            await conn.run_sync(lambda metadata: metadata.create_all(
                tables=[DailyStatsModel.__table__]
            ))
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise


class DatabaseClient:
    """Database client for interacting with PostgreSQL"""
    
    async def get_notification_logs(
        self,
        page: int = 1,
        page_size: int = 20,
        notification_type: Optional[NotificationType] = None,
        status: Optional[NotificationStatus] = None,
        user_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Tuple[List[NotificationDeliveryLog], int]:
        """
        Get notification delivery logs with pagination and filtering
        
        Args:
            page: Page number (1-based)
            page_size: Number of items per page
            notification_type: Filter by notification type
            status: Filter by status
            user_id: Filter by user ID
            start_date: Filter by start date
            end_date: Filter by end date
            
        Returns:
            Tuple[List[NotificationDeliveryLog], int]: (logs, total_count)
        """
        try:
            async with async_session() as session:
                # Build combined query for all notification types
                logs = []
                total_count = 0
                
                # Apply notification type filter
                if not notification_type or notification_type == NotificationType.EMAIL:
                    # Query email logs
                    email_query = sa.select(EmailDeliveryLogModel)
                    
                    # Apply filters
                    if status:
                        email_query = email_query.where(EmailDeliveryLogModel.status == status)
                    if user_id:
                        email_query = email_query.where(EmailDeliveryLogModel.user_id == user_id)
                    if start_date:
                        email_query = email_query.where(EmailDeliveryLogModel.created_at >= start_date)
                    if end_date:
                        email_query = email_query.where(EmailDeliveryLogModel.created_at <= end_date)
                    
                    # Execute query
                    result = await session.execute(email_query)
                    email_logs = result.scalars().all()
                    
                    # Convert to Pydantic models
                    for log in email_logs:
                        logs.append(NotificationDeliveryLog(
                            id=log.id,
                            notification_id=log.notification_id,
                            user_id=log.user_id,
                            type=NotificationType.EMAIL,
                            status=log.status,
                            provider=log.provider,
                            subject=log.subject,
                            body=None,  # Don't include email body for privacy
                            sent_at=log.sent_at,
                            delivered_at=log.delivered_at,
                            error_message=log.error_message,
                            retry_count=log.retry_count,
                            metadata=log.metadata,
                            created_at=log.created_at,
                            updated_at=log.updated_at
                        ))
                
                if not notification_type or notification_type == NotificationType.SMS:
                    # Query SMS logs
                    sms_query = sa.select(SMSDeliveryLogModel)
                    
                    # Apply filters
                    if status:
                        sms_query = sms_query.where(SMSDeliveryLogModel.status == status)
                    if user_id:
                        sms_query = sms_query.where(SMSDeliveryLogModel.user_id == user_id)
                    if start_date:
                        sms_query = sms_query.where(SMSDeliveryLogModel.created_at >= start_date)
                    if end_date:
                        sms_query = sms_query.where(SMSDeliveryLogModel.created_at <= end_date)
                    
                    # Execute query
                    result = await session.execute(sms_query)
                    sms_logs = result.scalars().all()
                    
                    # Convert to Pydantic models
                    for log in sms_logs:
                        logs.append(NotificationDeliveryLog(
                            id=log.id,
                            notification_id=log.notification_id,
                            user_id=log.user_id,
                            type=NotificationType.SMS,
                            status=log.status,
                            provider=log.provider,
                            subject=None,
                            body=log.body,
                            sent_at=log.sent_at,
                            delivered_at=log.delivered_at,
                            error_message=log.error_message,
                            retry_count=log.retry_count,
                            metadata=log.metadata,
                            created_at=log.created_at,
                            updated_at=log.updated_at
                        ))
                
                if not notification_type or notification_type == NotificationType.PUSH:
                    # Query push logs
                    push_query = sa.select(PushDeliveryLogModel)
                    
                    # Apply filters
                    if status:
                        push_query = push_query.where(PushDeliveryLogModel.status == status)
                    if user_id:
                        push_query = push_query.where(PushDeliveryLogModel.user_id == user_id)
                    if start_date:
                        push_query = push_query.where(PushDeliveryLogModel.created_at >= start_date)
                    if end_date:
                        push_query = push_query.where(PushDeliveryLogModel.created_at <= end_date)
                    
                    # Execute query
                    result = await session.execute(push_query)
                    push_logs = result.scalars().all()
                    
                    # Convert to Pydantic models
                    for log in push_logs:
                        logs.append(NotificationDeliveryLog(
                            id=log.id,
                            notification_id=log.notification_id,
                            user_id=log.user_id,
                            type=NotificationType.PUSH,
                            status=log.status,
                            provider=log.provider,
                            subject=log.title,
                            body=log.body,
                            sent_at=log.sent_at,
                            delivered_at=log.delivered_at,
                            error_message=log.error_message,
                            retry_count=log.retry_count,
                            metadata=log.metadata,
                            created_at=log.created_at,
                            updated_at=log.updated_at
                        ))
                
                # Sort logs by created_at date (newest first)
                logs.sort(key=lambda x: x.created_at, reverse=True)
                
                # Calculate total count and pagination
                total_count = len(logs)
                start_idx = (page - 1) * page_size
                end_idx = start_idx + page_size
                paginated_logs = logs[start_idx:end_idx] if start_idx < total_count else []
                
                return paginated_logs, total_count
                
        except Exception as e:
            logger.error(f"Error getting notification logs: {str(e)}")
            return [], 0
            
    async def get_notification_detail(self, notification_id: str) -> List[NotificationDeliveryLog]:
        """
        Get details for a specific notification across all channels
        
        Args:
            notification_id: Notification ID
            
        Returns:
            List[NotificationDeliveryLog]: Notification logs
        """
        try:
            async with async_session() as session:
                logs = []
                
                # Query email logs
                email_query = sa.select(EmailDeliveryLogModel).where(
                    EmailDeliveryLogModel.notification_id == notification_id
                )
                result = await session.execute(email_query)
                email_logs = result.scalars().all()
                
                # Convert to Pydantic models
                for log in email_logs:
                    logs.append(NotificationDeliveryLog(
                        id=log.id,
                        notification_id=log.notification_id,
                        user_id=log.user_id,
                        type=NotificationType.EMAIL,
                        status=log.status,
                        provider=log.provider,
                        subject=log.subject,
                        body=None,  # Don't include email body for privacy
                        sent_at=log.sent_at,
                        delivered_at=log.delivered_at,
                        error_message=log.error_message,
                        retry_count=log.retry_count,
                        metadata=log.metadata,
                        created_at=log.created_at,
                        updated_at=log.updated_at
                    ))
                
                # Query SMS logs
                sms_query = sa.select(SMSDeliveryLogModel).where(
                    SMSDeliveryLogModel.notification_id == notification_id
                )
                result = await session.execute(sms_query)
                sms_logs = result.scalars().all()
                
                # Convert to Pydantic models
                for log in sms_logs:
                    logs.append(NotificationDeliveryLog(
                        id=log.id,
                        notification_id=log.notification_id,
                        user_id=log.user_id,
                        type=NotificationType.SMS,
                        status=log.status,
                        provider=log.provider,
                        subject=None,
                        body=log.body,
                        sent_at=log.sent_at,
                        delivered_at=log.delivered_at,
                        error_message=log.error_message,
                        retry_count=log.retry_count,
                        metadata=log.metadata,
                        created_at=log.created_at,
                        updated_at=log.updated_at
                    ))
                
                # Query push logs
                push_query = sa.select(PushDeliveryLogModel).where(
                    PushDeliveryLogModel.notification_id == notification_id
                )
                result = await session.execute(push_query)
                push_logs = result.scalars().all()
                
                # Convert to Pydantic models
                for log in push_logs:
                    logs.append(NotificationDeliveryLog(
                        id=log.id,
                        notification_id=log.notification_id,
                        user_id=log.user_id,
                        type=NotificationType.PUSH,
                        status=log.status,
                        provider=log.provider,
                        subject=log.title,
                        body=log.body,
                        sent_at=log.sent_at,
                        delivered_at=log.delivered_at,
                        error_message=log.error_message,
                        retry_count=log.retry_count,
                        metadata=log.metadata,
                        created_at=log.created_at,
                        updated_at=log.updated_at
                    ))
                
                # Sort logs by created_at date
                logs.sort(key=lambda x: x.created_at)
                
                return logs
                
        except Exception as e:
            logger.error(f"Error getting notification detail: {str(e)}")
            return []
    
    async def get_notification_stats(
        self,
        time_range: TimeRange,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Tuple[NotificationStats, List[DailyStats]]:
        """
        Get notification statistics for a time range
        
        Args:
            time_range: Time range to query
            start_date: Start date for custom range
            end_date: End date for custom range
            
        Returns:
            Tuple[NotificationStats, List[DailyStats]]: (stats, daily_stats)
        """
        try:
            # Calculate date range based on time_range
            today = date.today()
            
            if time_range == TimeRange.TODAY:
                start_date = today
                end_date = today
            elif time_range == TimeRange.YESTERDAY:
                yesterday = today - timedelta(days=1)
                start_date = yesterday
                end_date = yesterday
            elif time_range == TimeRange.LAST_7_DAYS:
                start_date = today - timedelta(days=6)
                end_date = today
            elif time_range == TimeRange.LAST_30_DAYS:
                start_date = today - timedelta(days=29)
                end_date = today
            elif time_range == TimeRange.CUSTOM:
                if not start_date or not end_date:
                    raise ValueError("Custom time range requires start_date and end_date")
            else:
                raise ValueError(f"Invalid time range: {time_range}")
            
            # Convert dates to datetimes for querying
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())
            
            async with async_session() as session:
                # Initialize stats
                stats = NotificationStats(
                    total=0,
                    sent=0,
                    delivered=0,
                    failed=0,
                    pending=0,
                    retrying=0,
                    by_type={
                        NotificationType.EMAIL: 0,
                        NotificationType.SMS: 0,
                        NotificationType.PUSH: 0
                    },
                    by_status={
                        NotificationStatus.PENDING: 0,
                        NotificationStatus.SENT: 0,
                        NotificationStatus.DELIVERED: 0,
                        NotificationStatus.FAILED: 0,
                        NotificationStatus.RETRYING: 0
                    }
                )
                
                # Get email stats
                email_query = sa.select(
                    func.count().label("total"),
                    EmailDeliveryLogModel.status,
                ).where(
                    EmailDeliveryLogModel.created_at >= start_datetime,
                    EmailDeliveryLogModel.created_at <= end_datetime
                ).group_by(
                    EmailDeliveryLogModel.status
                )
                
                email_result = await session.execute(email_query)
                email_stats = email_result.all()
                
                for row in email_stats:
                    count, status = row
                    stats.total += count
                    stats.by_type[NotificationType.EMAIL] += count
                    
                    if status == "sent":
                        stats.sent += count
                        stats.by_status[NotificationStatus.SENT] += count
                    elif status == "delivered":
                        stats.delivered += count
                        stats.by_status[NotificationStatus.DELIVERED] += count
                    elif status == "failed":
                        stats.failed += count
                        stats.by_status[NotificationStatus.FAILED] += count
                    elif status == "pending":
                        stats.pending += count
                        stats.by_status[NotificationStatus.PENDING] += count
                    elif status == "retrying":
                        stats.retrying += count
                        stats.by_status[NotificationStatus.RETRYING] += count
                
                # Get Push stats
                push_query = sa.select(
                    func.count().label("total"),
                    PushDeliveryLogModel.status,
                ).where(
                    PushDeliveryLogModel.created_at >= start_datetime,
                    PushDeliveryLogModel.created_at <= end_datetime
                ).group_by(
                    PushDeliveryLogModel.status
                )
                
                push_result = await session.execute(push_query)
                push_stats = push_result.all()
                
                for row in push_stats:
                    count, status = row
                    stats.total += count
                    stats.by_type[NotificationType.PUSH] += count
                    
                    if status == "sent":
                        stats.sent += count
                        stats.by_status[NotificationStatus.SENT] += count
                    elif status == "delivered":
                        stats.delivered += count
                        stats.by_status[NotificationStatus.DELIVERED] += count
                    elif status == "failed":
                        stats.failed += count
                        stats.by_status[NotificationStatus.FAILED] += count
                    elif status == "pending":
                        stats.pending += count
                        stats.by_status[NotificationStatus.PENDING] += count
                    elif status == "retrying":
                        stats.retrying += count
                        stats.by_status[NotificationStatus.RETRYING] += count
                
                # Get SMS stats
                sms_query = sa.select(
                    func.count().label("total"),
                    SMSDeliveryLogModel.status,
                ).where(
                    SMSDeliveryLogModel.created_at >= start_datetime,
                    SMSDeliveryLogModel.created_at <= end_datetime
                ).group_by(
                    SMSDeliveryLogModel.status
                )
                
                sms_result = await session.execute(sms_query)
                sms_stats = sms_result.all()
                
                for row in sms_stats:
                    count, status = row
                    stats.total += count
                    stats.by_type[NotificationType.SMS] += count
                    
                    if status == "sent":
                        stats.sent += count
                        stats.by_status[NotificationStatus.SENT] += count
                    elif status == "delivered":
                        stats.delivered += count
                        stats.by_status[NotificationStatus.DELIVERED] += count
                    elif status == "failed":
                        stats.failed += count
                        stats.by_status[NotificationStatus.FAILED] += count
                    elif status == "pending":
                        stats.pending += count
                        stats.by_status[NotificationStatus.PENDING] += count
                    elif status == "retrying":
                        stats.retrying += count
                        stats.by_status[NotificationStatus.RETRYING] += count
                
                # Get daily stats for the date range
                daily_stats_list = []
                
                # Generate a list of dates in the range
                date_range = []
                current_date = start_date
                while current_date <= end_date:
                    date_range.append(current_date)
                    current_date = current_date + timedelta(days=1)
                
                # Query for existing daily stats from our cache table
                daily_stats_query = sa.select(DailyStatsModel).where(
                    DailyStatsModel.date.between(start_date, end_date)
                ).order_by(DailyStatsModel.date)
                
                daily_stats_result = await session.execute(daily_stats_query)
                existing_daily_stats = {stat.date: stat for stat in daily_stats_result.scalars().all()}
                
                # Fill in any missing dates with calculated stats
                for day in date_range:
                    if day in existing_daily_stats:
                        # Use cached stats
                        stat = existing_daily_stats[day]
                        daily_stats_list.append(DailyStats(
                            date=stat.date,
                            total=stat.total,
                            email=stat.email,
                            sms=stat.sms,
                            push=stat.push,
                            sent=stat.sent,
                            delivered=stat.delivered,
                            failed=stat.failed
                        ))
                    else:
                        # Calculate stats for this day
                        day_start = datetime.combine(day, datetime.min.time())
                        day_end = datetime.combine(day, datetime.max.time())
                        
                        # Email count for the day
                        email_count_query = sa.select(func.count()).where(
                            EmailDeliveryLogModel.created_at.between(day_start, day_end)
                        )
                        email_count = await session.scalar(email_count_query) or 0
                        
                        # SMS count for the day
                        sms_count_query = sa.select(func.count()).where(
                            SMSDeliveryLogModel.created_at.between(day_start, day_end)
                        )
                        sms_count = await session.scalar(sms_count_query) or 0
                        
                        # Push count for the day
                        push_count_query = sa.select(func.count()).where(
                            PushDeliveryLogModel.created_at.between(day_start, day_end)
                        )
                        push_count = await session.scalar(push_count_query) or 0
                        
                        # Status counts for the day
                        sent_count = 0
                        delivered_count = 0
                        failed_count = 0
                        
                        # Email status counts
                        email_status_query = sa.select(
                            EmailDeliveryLogModel.status,
                            func.count().label("count")
                        ).where(
                            EmailDeliveryLogModel.created_at.between(day_start, day_end)
                        ).group_by(
                            EmailDeliveryLogModel.status
                        )
                        email_status_result = await session.execute(email_status_query)
                        
                        for row in email_status_result:
                            status, count = row
                            if status == "sent":
                                sent_count += count
                            elif status == "delivered":
                                delivered_count += count
                            elif status == "failed":
                                failed_count += count
                        
                        # SMS status counts
                        sms_status_query = sa.select(
                            SMSDeliveryLogModel.status,
                            func.count().label("count")
                        ).where(
                            SMSDeliveryLogModel.created_at.between(day_start, day_end)
                        ).group_by(
                            SMSDeliveryLogModel.status
                        )
                        sms_status_result = await session.execute(sms_status_query)
                        
                        for row in sms_status_result:
                            status, count = row
                            if status == "sent":
                                sent_count += count
                            elif status == "delivered":
                                delivered_count += count
                            elif status == "failed":
                                failed_count += count
                        
                        # Push status counts
                        push_status_query = sa.select(
                            PushDeliveryLogModel.status,
                            func.count().label("count")
                        ).where(
                            PushDeliveryLogModel.created_at.between(day_start, day_end)
                        ).group_by(
                            PushDeliveryLogModel.status
                        )
                        push_status_result = await session.execute(push_status_query)
                        
                        for row in push_status_result:
                            status, count = row
                            if status == "sent":
                                sent_count += count
                            elif status == "delivered":
                                delivered_count += count
                            elif status == "failed":
                                failed_count += count
                        
                        # Total for the day
                        total_count = email_count + sms_count + push_count
                        
                        # Create daily stats
                        daily_stats = DailyStats(
                            date=day,
                            total=total_count,
                            email=email_count,
                            sms=sms_count,
                            push=push_count,
                            sent=sent_count,
                            delivered=delivered_count,
                            failed=failed_count
                        )
                        
                        daily_stats_list.append(daily_stats)
                        
                        # Cache the daily stats for future queries
                        daily_stats_model = DailyStatsModel(
                            date=day,
                            total=total_count,
                            email=email_count,
                            sms=sms_count,
                            push=push_count,
                            sent=sent_count,
                            delivered=delivered_count,
                            failed=failed_count
                        )
                        
                        session.add(daily_stats_model)
                
                # Commit cached stats
                await session.commit()
                
                return stats, daily_stats_list
                
        except Exception as e:
            logger.error(f"Error getting notification stats: {str(e)}")
            return NotificationStats(
                total=0,
                sent=0,
                delivered=0,
                failed=0,
                pending=0,
                retrying=0,
                by_type={
                    NotificationType.EMAIL: 0,
                    NotificationType.SMS: 0,
                    NotificationType.PUSH: 0
                },
                by_status={
                    NotificationStatus.PENDING: 0,
                    NotificationStatus.SENT: 0,
                    NotificationStatus.DELIVERED: 0,
                    NotificationStatus.FAILED: 0,
                    NotificationStatus.RETRYING: 0
                }
            ), []


# Singleton instance
db_client = DatabaseClient()