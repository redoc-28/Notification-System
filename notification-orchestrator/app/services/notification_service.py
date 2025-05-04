import logging
import uuid
import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from app.core.config import get_settings
from app.core.rabbitmq import rabbitmq_client
from app.models.notification import (
    NotificationType, 
    NotificationRequest, 
    NotificationResponse, 
    NotificationStatus,
    BulkNotificationRequest,
    BulkNotificationResponse
)
from app.services.deduplication import deduplication_service
from app.services.rate_limit import rate_limit_service

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Main service for handling notification requests and routing them to 
    appropriate services through RabbitMQ
    """
    
    def __init__(self):
        self.settings = get_settings()
        
    async def send_notification(self, request: NotificationRequest) -> NotificationResponse:
        """
        Process a notification request
        
        Args:
            request: NotificationRequest model with notification details
            
        Returns:
            NotificationResponse: Response with notification ID and status
        """
        # Check for duplicate if idempotency key is provided
        if request.idempotency_key:
            existing_id = await deduplication_service.get_existing_notification_id(
                request.idempotency_key
            )
            if existing_id:
                logger.info(f"Duplicate notification detected with key: {request.idempotency_key}")
                return NotificationResponse(
                    notification_id=existing_id,
                    status=NotificationStatus.SENT,
                    created_at=datetime.now(),
                    idempotency_key=request.idempotency_key,
                    scheduled_at=request.scheduled_at
                )
        
        # Generate notification ID
        notification_id = str(uuid.uuid4())
        
        # Check rate limits and process each notification type
        results = []
        for notification_type in request.types:
            # Check rate limit
            rate_limited = await rate_limit_service.check_rate_limit(
                request.user_id, 
                notification_type
            )
            
            if rate_limited:
                logger.warning(
                    f"Rate limit exceeded for user {request.user_id} "
                    f"and type {notification_type.value}"
                )
                results.append((notification_type, False, "Rate limit exceeded"))
                continue
            
            # Process notification
            success, error = await self._process_notification(
                notification_id=notification_id,
                notification_type=notification_type,
                user_id=request.user_id,
                request=request
            )
            
            # Increment rate limit counter if successful
            if success:
                await rate_limit_service.increment_counter(request.user_id, notification_type)
                
            results.append((notification_type, success, error))
        
        # Determine overall status
        status = NotificationStatus.SENT
        if not any(success for _, success, _ in results):
            status = NotificationStatus.FAILED
        elif not all(success for _, success, _ in results):
            status = NotificationStatus.PARTIALLY_SENT
            
        # Mark as processed for deduplication if idempotency key is provided
        if request.idempotency_key:
            await deduplication_service.mark_as_processed(
                request.idempotency_key,
                notification_id
            )
            
        # Return response
        return NotificationResponse(
            notification_id=notification_id,
            status=status,
            created_at=datetime.now(),
            idempotency_key=request.idempotency_key,
            scheduled_at=request.scheduled_at
        )
        
    async def _process_notification(
        self, 
        notification_id: str,
        notification_type: NotificationType,
        user_id: str,
        request: NotificationRequest
    ) -> Tuple[bool, Optional[str]]:
        """
        Process a single notification type for a request
        
        Args:
            notification_id: Generated notification ID
            notification_type: Type of notification (email, sms, push)
            user_id: User ID
            request: The original notification request
            
        Returns:
            Tuple[bool, Optional[str]]: (success, error_message)
        """
        try:
            # Prepare message based on notification type
            routing_key = f"notification.{notification_type.value}"
            
            # Extract content for this notification type
            content = None
            if notification_type == NotificationType.EMAIL and request.content.email:
                content = request.content.email.dict()
            elif notification_type == NotificationType.SMS and request.content.sms:
                content = request.content.sms.dict()
            elif notification_type == NotificationType.PUSH and request.content.push:
                content = request.content.push.dict()
                
            if not content:
                return False, f"No content provided for {notification_type.value}"
                
            # Prepare message
            message_data = {
                "notification_id": notification_id,
                "type": notification_type.value,
                "user_id": user_id,
                "content": content,
                "priority": request.priority.value,
                "metadata": request.metadata or {},
                "created_at": datetime.now().isoformat(),
                "scheduled_at": request.scheduled_at.isoformat() if request.scheduled_at else None
            }
            
            # Determine message priority (0-9) based on notification priority
            priority_map = {
                "low": 1,
                "medium": 5,
                "high": 9
            }
            message_priority = priority_map.get(request.priority.value, 5)
            
            # Add retry count in headers
            headers = {
                "retry_count": 0,
                "max_retries": self.settings.MAX_RETRIES
            }
            
            # Publish message to appropriate queue
            success = await rabbitmq_client.publish_message(
                routing_key=routing_key,
                message_data=message_data,
                headers=headers,
                priority=message_priority
            )
            
            if success:
                logger.info(
                    f"Successfully queued {notification_type.value} notification "
                    f"for user {user_id}, notification_id: {notification_id}"
                )
                return True, None
            else:
                logger.error(
                    f"Failed to queue {notification_type.value} notification "
                    f"for user {user_id}, notification_id: {notification_id}"
                )
                return False, "Failed to queue notification"
                
        except Exception as e:
            logger.exception(
                f"Error processing {notification_type.value} notification: {str(e)}"
            )
            return False, str(e)
            
            
    async def send_bulk_notifications(
        self, 
        request: BulkNotificationRequest
    ) -> BulkNotificationResponse:
        """
        Process multiple notification requests
        
        Args:
            request: BulkNotificationRequest with multiple notifications
            
        Returns:
            BulkNotificationResponse: Aggregated response for all notifications
        """
        responses = []
        successful = 0
        
        for notification_request in request.notifications:
            response = await self.send_notification(notification_request)
            responses.append(response)
            
            if response.status == NotificationStatus.SENT:
                successful += 1
                
        # Generate batch ID if not provided
        batch_id = request.batch_id or str(uuid.uuid4())
        
        return BulkNotificationResponse(
            batch_id=batch_id,
            total=len(request.notifications),
            successful=successful,
            failed=len(request.notifications) - successful,
            notifications=responses
        )


# Singleton instance
notification_service = NotificationService()