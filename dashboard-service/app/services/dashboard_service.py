import logging
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, date

from app.core.config import get_settings
from app.models.dashboard import (
    NotificationType,
    NotificationStatus,
    TimeRange,
    NotificationDeliveryLog,
    NotificationStats,
    DailyStats,
    StatsResponse,
    NotificationLogsResponse,
    NotificationDetailResponse
)
from app.db.database import db_client

logger = logging.getLogger(__name__)


class DashboardService:
    """Service for providing notification system analytics and monitoring"""
    
    def __init__(self):
        self.settings = get_settings()
        
    async def get_notification_logs(
        self,
        page: int = 1,
        page_size: int = 20,
        notification_type: Optional[NotificationType] = None,
        status: Optional[NotificationStatus] = None,
        user_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> NotificationLogsResponse:
        """
        Get notification logs with pagination and filtering
        
        Args:
            page: Page number (1-based)
            page_size: Number of items per page
            notification_type: Filter by notification type
            status: Filter by status
            user_id: Filter by user ID
            start_date: Filter by start date
            end_date: Filter by end date
            
        Returns:
            NotificationLogsResponse: Paginated notification logs with metadata
        """
        # Validate page_size
        if page_size > self.settings.MAX_PAGE_SIZE:
            page_size = self.settings.MAX_PAGE_SIZE
        
        # Get logs from database
        logs, total_count = await db_client.get_notification_logs(
            page=page,
            page_size=page_size,
            notification_type=notification_type,
            status=status,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date
        )
        
        # Create response
        return NotificationLogsResponse(
            total=total_count,
            page=page,
            page_size=page_size,
            logs=logs
        )
        
    async def get_notification_detail(self, notification_id: str) -> NotificationDetailResponse:
        """
        Get detailed information about a specific notification
        
        Args:
            notification_id: Notification ID
            
        Returns:
            NotificationDetailResponse: Detailed notification information
        """
        # Get logs from database
        logs = await db_client.get_notification_detail(notification_id)
        
        # Create response
        return NotificationDetailResponse(
            notification_id=notification_id,
            logs=logs
        )
        
    async def get_stats(
        self,
        time_range: TimeRange,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> StatsResponse:
        """
        Get notification statistics for a time range
        
        Args:
            time_range: Time range to query
            start_date: Start date for custom range
            end_date: End date for custom range
            
        Returns:
            StatsResponse: Notification statistics
        """
        # Get stats from database
        stats, daily_stats = await db_client.get_notification_stats(
            time_range=time_range,
            start_date=start_date,
            end_date=end_date
        )
        
        # Create response
        return StatsResponse(
            time_range=time_range,
            start_date=start_date,
            end_date=end_date,
            stats=stats,
            daily_stats=daily_stats
        )


# Singleton instance
dashboard_service = DashboardService()