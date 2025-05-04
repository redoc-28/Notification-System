import logging
import uuid
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import json

from app.core.settings import get_settings
from app.models.push import PushStatus, PushMessage
from app.db.database import db_client

logger = logging.getLogger(__name__)


class PushService:
    """Service for sending push notifications using various providers"""
    
    def __init__(self):
        self.settings = get_settings()
        
    async def process_push(self, message_data: Dict[str, Any], headers: Dict[str, Any]) -> bool:
        """
        Process a push notification message from RabbitMQ
        
        Args:
            message_data: Message data
            headers: Message headers
            
        Returns:
            bool: Success status
        """
        try:
            # Extract data from message
            notification_id = message_data.get("notification_id")
            user_id = message_data.get("user_id")
            content = message_data.get("content", {})
            metadata = message_data.get("metadata", {})
            
            # Check if required fields are present
            if not all([notification_id, user_id, content, content.get("title"), content.get("body")]):
                logger.error(f"Missing required fields in message: {notification_id}")
                return False
            
            # Create PushMessage object
            push_message = PushMessage(
                notification_id=notification_id,
                user_id=user_id,
                title=content.get("title", ""),
                body=content.get("body", ""),
                data=content.get("data"),
                image_url=content.get("image_url"),
                action_url=content.get("action_url"),
                metadata=metadata,
                created_at=datetime.fromisoformat(message_data.get("created_at", datetime.now().isoformat())),
                scheduled_at=datetime.fromisoformat(message_data.get("scheduled_at")) if message_data.get("scheduled_at") else None,
                priority=message_data.get("priority", "medium")
            )
            
            # Get retry count from headers
            retry_count = headers.get("retry_count", 0)
            
            # Generate log ID
            log_id = str(uuid.uuid4())
            
            # Log initial attempt
            await db_client.log_push_delivery(
                log_id=log_id,
                notification_id=notification_id,
                user_id=user_id,
                provider=self.settings.PUSH_PROVIDER,
                status=PushStatus.PENDING,
                title=push_message.title,
                body=push_message.body,
                image_url=push_message.image_url,
                action_url=push_message.action_url,
                retry_count=retry_count,
                metadata=metadata
            )
            
            # Send the push notification
            success, provider_message_id, error_message = await self._send_push(push_message)
            
            # Update status based on result
            status = PushStatus.SENT if success else PushStatus.FAILED
            sent_at = datetime.now() if success else None
            
            # Update log with result
            await db_client.update_push_status(
                log_id=log_id,
                status=status,
                provider_message_id=provider_message_id,
                error_message=error_message
            )
            
            if success:
                logger.info(f"Push notification sent successfully: {notification_id}")
            else:
                logger.error(f"Failed to send push notification: {notification_id}, error: {error_message}")
                
            return success
            
        except Exception as e:
            logger.exception(f"Error processing push notification: {str(e)}")
            return False
            
    async def _send_push(self, push: PushMessage) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Send a push notification using the configured provider
        
        Args:
            push: PushMessage to send
            
        Returns:
            Tuple[bool, Optional[str], Optional[str]]: (success, provider_message_id, error_message)
        """
        # Get the push provider to use
        provider = self.settings.PUSH_PROVIDER.lower()
        
        try:
            if provider == "fcm":
                return await self._send_with_fcm(push)
            elif provider == "apn":
                return await self._send_with_apn(push)
            elif provider == "webpush":
                return await self._send_with_webpush(push)
            else:
                error_message = f"Unknown push provider: {provider}"
                logger.error(error_message)
                return False, None, error_message
                
        except Exception as e:
            error_message = f"Error sending push notification: {str(e)}"
            logger.exception(error_message)
            return False, None, error_message
    
    async def _send_with_fcm(self, push: PushMessage) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Send a push notification using Firebase Cloud Messaging (FCM)
        
        Args:
            push: PushMessage to send
            
        Returns:
            Tuple[bool, Optional[str], Optional[str]]: (success, provider_message_id, error_message)
        """
        try:
            # Import firebase_admin here to avoid dependency if not using
            import firebase_admin
            from firebase_admin import credentials, messaging
            
            # Check if FCM settings are configured
            if not self.settings.FCM_SERVER_KEY and not self.settings.FCM_SERVICE_ACCOUNT_JSON:
                return False, None, "FCM credentials not configured"
            
            # Initialize Firebase Admin SDK if not already initialized
            if not firebase_admin._apps:
                if self.settings.FCM_SERVICE_ACCOUNT_JSON:
                    # Use service account JSON
                    cred = credentials.Certificate(json.loads(self.settings.FCM_SERVICE_ACCOUNT_JSON))
                    firebase_admin.initialize_app(cred)
                else:
                    # Use default credentials (useful for Google Cloud)
                    firebase_admin.initialize_app()
            
            # Create FCM message
            message = messaging.Message(
                notification=messaging.Notification(
                    title=push.title,
                    body=push.body,
                    image=push.image_url
                ),
                data=push.data or {},
                token=push.user_id,  # Assuming user_id is the FCM token
            )
            
            # Send the message
            response = messaging.send(message)
            
            # Success
            return True, response, None
            
        except Exception as e:
            return False, None, f"FCM error: {str(e)}"
    
    async def _send_with_apn(self, push: PushMessage) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Send a push notification using Apple Push Notification service (APNs)
        
        Args:
            push: PushMessage to send
            
        Returns:
            Tuple[bool, Optional[str], Optional[str]]: (success, provider_message_id, error_message)
        """
        try:
            # Import aioapns here to avoid dependency if not using
            from aioapns import APNs, NotificationRequest, PushType
            
            # Check if APNs settings are configured
            if not all([self.settings.APN_KEY_ID, self.settings.APN_AUTH_KEY, self.settings.APN_TEAM_ID, self.settings.APN_BUNDLE_ID]):
                return False, None, "APNs credentials not configured"
            
            # Create APNs client
            client = APNs(
                key_id=self.settings.APN_KEY_ID,
                key=self.settings.APN_AUTH_KEY,
                team_id=self.settings.APN_TEAM_ID,
                bundle_id=self.settings.APN_BUNDLE_ID,
                use_sandbox=self.settings.DEBUG
            )
            
            # Create notification request
            request = NotificationRequest(
                device_token=push.user_id,  # Assuming user_id is the device token
                message={
                    "aps": {
                        "alert": {
                            "title": push.title,
                            "body": push.body
                        },
                        "mutable-content": 1 if push.image_url else 0,
                        "sound": "default"
                    },
                    "data": push.data or {}
                },
                push_type=PushType.ALERT
            )
            
            # Send notification
            response = await client.send_notification(request)
            
            # Check response
            if response.is_successful:
                return True, response.notification_id, None
            else:
                return False, None, response.description
                
        except Exception as e:
            return False, None, f"APNs error: {str(e)}"
            
    async def _send_with_webpush(self, push: PushMessage) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Send a push notification using Web Push
        
        Args:
            push: PushMessage to send
            
        Returns:
            Tuple[bool, Optional[str], Optional[str]]: (success, provider_message_id, error_message)
        """
        try:
            # Import pywebpush here to avoid dependency if not using
            from pywebpush import webpush, WebPushException
            
            # Check if Web Push settings are configured
            if not all([self.settings.VAPID_PRIVATE_KEY, self.settings.VAPID_PUBLIC_KEY, self.settings.VAPID_CLAIMS]):
                return False, None, "Web Push credentials not configured"
            
            # Create notification data
            data = {
                "title": push.title,
                "body": push.body,
                "icon": push.image_url,
                "data": push.data or {},
                "url": push.action_url
            }
            
            # Send notification
            response = webpush(
                subscription_info=json.loads(push.user_id),  # Assuming user_id is the subscription info JSON
                data=json.dumps(data),
                vapid_private_key=self.settings.VAPID_PRIVATE_KEY,
                vapid_claims=json.loads(self.settings.VAPID_CLAIMS)
            )
            
            # Check response
            if response.ok:
                return True, response.headers.get("Location"), None
            else:
                return False, None, f"HTTP {response.status_code}: {response.text}"
                
        except WebPushException as e:
            return False, None, f"Web Push error: {str(e)}"
        except Exception as e:
            return False, None, f"Web Push error: {str(e)}"


# Singleton instance
push_service = PushService()