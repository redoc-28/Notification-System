from typing import Dict, List, Optional, Any
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from enum import Enum


class EmailStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    BOUNCED = "bounced"


class EmailMessage(BaseModel):
    notification_id: str
    user_id: str
    subject: str
    body_text: str
    body_html: Optional[str] = None
    from_email: Optional[str] = None
    reply_to: Optional[str] = None
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None
    attachments: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    scheduled_at: Optional[datetime] = None
    priority: str = "medium"


class EmailDeliveryLog(BaseModel):
    notification_id: str
    user_id: str
    provider: str  # e.g., "sendgrid", "ses"
    status: EmailStatus
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    provider_message_id: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    metadata: Optional[Dict[str, Any]] = None