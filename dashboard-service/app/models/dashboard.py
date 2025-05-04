from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime, date
from enum import Enum


class NotificationType(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"


class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


class TimeRange(str, Enum):
    TODAY = "today"
    YESTERDAY = "yesterday"
    LAST_7_DAYS = "last_7_days"
    LAST_30_DAYS = "last_30_days"
    CUSTOM = "custom"


class NotificationDeliveryLog(BaseModel):
    id: str
    notification_id: str
    user_id: str
    type: NotificationType
    status: NotificationStatus
    provider: str
    subject: Optional[str] = None
    body: Optional[str] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime


class NotificationStats(BaseModel):
    total: int
    sent: int
    delivered: int
    failed: int
    pending: int
    retrying: int
    by_type: Dict[NotificationType, int]
    by_status: Dict[NotificationStatus, int]


class DailyStats(BaseModel):
    date: date
    total: int
    email: int
    sms: int
    push: int
    sent: int
    delivered: int
    failed: int


class StatsResponse(BaseModel):
    time_range: TimeRange
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    stats: NotificationStats
    daily_stats: List[DailyStats]


class NotificationLogsResponse(BaseModel):
    total: int
    page: int
    page_size: int
    logs: List[NotificationDeliveryLog]


class NotificationDetailResponse(BaseModel):
    notification_id: str
    logs: List[NotificationDeliveryLog]