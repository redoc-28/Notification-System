import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from app.core.config import get_settings
from app.models.preferences import (
    UserPreferences, 
    PreferenceUpdateRequest,
    PreferenceResponse,
    NotificationChannel,
    NotificationCategory,
    ChannelPreference,
    CategoryPreference
)
from app.db.database import db_client

logger = logging.getLogger(__name__)


class PreferencesService:
    """Service for managing user notification preferences"""
    
    def __init__(self):
        self.settings = get_settings()
        
    async def get_user_preferences(self, user_id: str) -> Tuple[Optional[UserPreferences], str]:
        """
        Get user notification preferences
        
        Args:
            user_id: User ID
            
        Returns:
            Tuple[Optional[UserPreferences], str]: (preferences, message)
        """
        # Get user preferences from database
        preferences = await db_client.get_user_preferences(user_id)
        
        if preferences:
            return preferences, "Preferences retrieved successfully"
        else:
            # Create default preferences if not found
            default_prefs = self._create_default_preferences(user_id)
            success = await db_client.create_user_preferences(default_prefs)
            
            if success:
                return default_prefs, "Default preferences created successfully"
            else:
                return None, "Failed to create default preferences"
    
    async def update_user_preferences(self, user_id: str, update_request: PreferenceUpdateRequest) -> Tuple[Optional[UserPreferences], str]:
        """
        Update user notification preferences
        
        Args:
            user_id: User ID
            update_request: PreferenceUpdateRequest with fields to update
            
        Returns:
            Tuple[Optional[UserPreferences], str]: (updated_preferences, message)
        """
        # Get current preferences
        current_prefs, _ = await self.get_user_preferences(user_id)
        if not current_prefs:
            return None, "Failed to retrieve user preferences"
        
        # Update fields based on request
        if update_request.channels is not None:
            current_prefs.channels.update(update_request.channels)
            
        if update_request.categories is not None:
            current_prefs.categories.update(update_request.categories)
            
        if update_request.do_not_disturb is not None:
            current_prefs.do_not_disturb = update_request.do_not_disturb
            
        if update_request.timezone is not None:
            current_prefs.timezone = update_request.timezone
            
        # Update timestamp
        current_prefs.updated_at = datetime.utcnow()
        
        # Save to database
        success = await db_client.update_user_preferences(current_prefs)
        
        if success:
            return current_prefs, "Preferences updated successfully"
        else:
            return None, "Failed to update preferences"
    
    async def delete_user_preferences(self, user_id: str) -> Tuple[bool, str]:
        """
        Delete user notification preferences
        
        Args:
            user_id: User ID
            
        Returns:
            Tuple[bool, str]: (success, message)
        """
        # Delete from database
        success = await db_client.delete_user_preferences(user_id)
        
        if success:
            return True, "Preferences deleted successfully"
        else:
            return False, "Failed to delete preferences"
    
    def _create_default_preferences(self, user_id: str) -> UserPreferences:
        """
        Create default preferences for a new user
        
        Args:
            user_id: User ID
            
        Returns:
            UserPreferences: Default user preferences
        """
        # Default channel preferences
        default_channel_pref = ChannelPreference(
            enabled=self.settings.DEFAULT_CHANNEL_ENABLED,
            quiet_hours_start=None,
            quiet_hours_end=None,
            frequency_limit=None,
            urgent_override=True
        )
        
        # Default category preferences
        default_category_pref = CategoryPreference(
            enabled=self.settings.DEFAULT_CATEGORY_ENABLED,
            channels={
                NotificationChannel.EMAIL: True,
                NotificationChannel.SMS: True,
                NotificationChannel.PUSH: True
            }
        )
        
        # Special case for marketing category - opt-in by default for email only
        marketing_pref = CategoryPreference(
            enabled=True,
            channels={
                NotificationChannel.EMAIL: True,
                NotificationChannel.SMS: False,
                NotificationChannel.PUSH: False
            }
        )
        
        # Create default preferences
        return UserPreferences(
            user_id=user_id,
            channels={
                NotificationChannel.EMAIL: default_channel_pref,
                NotificationChannel.SMS: default_channel_pref,
                NotificationChannel.PUSH: default_channel_pref
            },
            categories={
                NotificationCategory.ACCOUNT: default_category_pref,
                NotificationCategory.MARKETING: marketing_pref,
                NotificationCategory.TRANSACTIONS: default_category_pref,
                NotificationCategory.UPDATES: default_category_pref,
                NotificationCategory.ALERTS: default_category_pref,
                NotificationCategory.NEWS: default_category_pref
            },
            do_not_disturb=self.settings.DEFAULT_DO_NOT_DISTURB,
            timezone=self.settings.DEFAULT_TIMEZONE,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
    
    async def is_notification_allowed(
        self, 
        user_id: str, 
        channel: NotificationChannel, 
        category: NotificationCategory,
        is_urgent: bool = False
    ) -> bool:
        """
        Check if a notification is allowed based on user preferences
        
        Args:
            user_id: User ID
            channel: Notification channel (email, sms, push)
            category: Notification category
            is_urgent: Whether this is an urgent notification
            
        Returns:
            bool: True if allowed, False otherwise
        """
        # Get user preferences
        preferences, _ = await self.get_user_preferences(user_id)
        if not preferences:
            # Default to allowed if preferences not found
            return True
        
        # Check global do not disturb
        if preferences.do_not_disturb and not is_urgent:
            return False
        
        # Check channel enabled
        channel_pref = preferences.channels.get(channel)
        if not channel_pref or not channel_pref.enabled:
            # Allow if urgent and urgent override is enabled
            if is_urgent and channel_pref and channel_pref.urgent_override:
                return True
            return False
        
        # Check category enabled
        category_pref = preferences.categories.get(category)
        if not category_pref or not category_pref.enabled:
            return False
        
        # Check category channel enabled
        channel_enabled = category_pref.channels.get(channel, True)
        if not channel_enabled:
            return False
        
        # TODO: Check quiet hours and frequency limits
        # This would require additional time-based logic
        
        # All checks passed
        return True


# Singleton instance
preferences_service = PreferencesService()