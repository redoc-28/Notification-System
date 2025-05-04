from typing import Dict, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class SMSStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"


class SMSMessage(BaseModel):
    notification_id: str
    user_id: str
    body: str
    sender_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    scheduled_at: Optional[datetime] = None
    priority: str = "medium"


class SMSDeliveryLog(BaseModel):
    notification_id: str
    user_id: str
    provider: str  # e.g., "twilio", "sns"
    status: SMSStatus
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    provider_message_id: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    metadata: Optional[Dict[str, Any]] = None