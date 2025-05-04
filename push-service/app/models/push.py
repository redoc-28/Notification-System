from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class PushStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"


class PushMessage(BaseModel):
    notification_id: str
    user_id: str
    title: str
    body: str
    data: Optional[Dict[str, Any]] = None
    image_url: Optional[str] = None
    action_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    scheduled_at: Optional[datetime] = None
    priority: str = "medium"


class PushDeliveryLog(BaseModel):
    notification_id: str
    user_id: str
    provider: str  # e.g., "fcm", "apn", "webpush"
    status: PushStatus
    title: str
    body: str
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    provider_message_id: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    metadata: Optional[Dict[str, Any]] = None