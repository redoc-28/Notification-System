from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime, time
from enum import Enum


class NotificationChannel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"


class NotificationCategory(str, Enum):
    ACCOUNT = "account"
    MARKETING = "marketing"
    TRANSACTIONS = "transactions"
    UPDATES = "updates"
    ALERTS = "alerts"
    NEWS = "news"


class ChannelPreference(BaseModel):
    enabled: bool = True
    quiet_hours_start: Optional[time] = None
    quiet_hours_end: Optional[time] = None
    frequency_limit: Optional[int] = None  # Max notifications per day
    urgent_override: bool = True  # Allow urgent notifications during quiet hours


class CategoryPreference(BaseModel):
    enabled: bool = True
    channels: Dict[NotificationChannel, bool] = Field(
        default_factory=lambda: {
            NotificationChannel.EMAIL: True,
            NotificationChannel.SMS: True,
            NotificationChannel.PUSH: True
        }
    )


class UserPreferences(BaseModel):
    user_id: str
    channels: Dict[NotificationChannel, ChannelPreference] = Field(
        default_factory=lambda: {
            NotificationChannel.EMAIL: ChannelPreference(),
            NotificationChannel.SMS: ChannelPreference(),
            NotificationChannel.PUSH: ChannelPreference()
        }
    )
    categories: Dict[NotificationCategory, CategoryPreference] = Field(
        default_factory=lambda: {
            NotificationCategory.ACCOUNT: CategoryPreference(),
            NotificationCategory.MARKETING: CategoryPreference(),
            NotificationCategory.TRANSACTIONS: CategoryPreference(),
            NotificationCategory.UPDATES: CategoryPreference(),
            NotificationCategory.ALERTS: CategoryPreference(),
            NotificationCategory.NEWS: CategoryPreference()
        }
    )
    do_not_disturb: bool = False
    timezone: Optional[str] = "UTC"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PreferenceUpdateRequest(BaseModel):
    channels: Optional[Dict[NotificationChannel, ChannelPreference]] = None
    categories: Optional[Dict[NotificationCategory, CategoryPreference]] = None
    do_not_disturb: Optional[bool] = None
    timezone: Optional[str] = None


class PreferenceResponse(BaseModel):
    user_id: str
    preferences: UserPreferences
    message: Optional[str] = None