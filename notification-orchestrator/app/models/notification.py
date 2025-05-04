from typing import Dict, List, Optional, Any
from enum import Enum
from pydantic import BaseModel, Field, validator
from datetime import datetime


class NotificationType(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"


class NotificationPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    RETRYING = "retrying"


class EmailContent(BaseModel):
    subject: str
    body_html: Optional[str] = None
    body_text: str
    from_email: Optional[str] = None
    reply_to: Optional[str] = None
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None
    attachments: Optional[List[Dict[str, Any]]] = None


class SMSContent(BaseModel):
    body: str
    sender_id: Optional[str] = None


class PushContent(BaseModel):
    title: str
    body: str
    data: Optional[Dict[str, Any]] = None
    image_url: Optional[str] = None
    action_url: Optional[str] = None


class NotificationContent(BaseModel):
    email: Optional[EmailContent] = None
    sms: Optional[SMSContent] = None
    push: Optional[PushContent] = None

    @validator('*', pre=True)
    def check_at_least_one(cls, v, values):
        if not v and not any(values.values()):
            raise ValueError("At least one notification type content must be provided")
        return v


class NotificationRequest(BaseModel):
    user_id: str
    types: List[NotificationType]
    content: NotificationContent
    priority: NotificationPriority = NotificationPriority.MEDIUM
    idempotency_key: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

    @validator('types')
    def validate_types_match_content(cls, v, values):
        if 'content' not in values:
            return v
        
        content = values['content']
        for notification_type in v:
            if notification_type == NotificationType.EMAIL and not content.email:
                raise ValueError("Email type specified but no email content provided")
            if notification_type == NotificationType.SMS and not content.sms:
                raise ValueError("SMS type specified but no SMS content provided")
            if notification_type == NotificationType.PUSH and not content.push:
                raise ValueError("Push type specified but no push content provided")
        return v


class NotificationResponse(BaseModel):
    notification_id: str
    status: NotificationStatus
    created_at: datetime
    idempotency_key: Optional[str] = None
    scheduled_at: Optional[datetime] = None


class BulkNotificationRequest(BaseModel):
    notifications: List[NotificationRequest]
    batch_id: Optional[str] = None

    @validator('notifications')
    def validate_non_empty(cls, v):
        if not v:
            raise ValueError("Notifications list cannot be empty")
        return v


class BulkNotificationResponse(BaseModel):
    batch_id: str
    total: int
    successful: int
    failed: int
    notifications: List[NotificationResponse]