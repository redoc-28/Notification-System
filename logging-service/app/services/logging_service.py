import logging
import uuid
import asyncio
from typing import Dict, Any, List
from datetime import datetime, timedelta
from collections import deque

from app.core.config import get_settings
from app.models.log import NotificationLogMessage, SystemLogMessage
from app.db.database import db_client

logger = logging.getLogger(__name__)


class LoggingService:
    """Service for processing and storing notification and system logs"""
    
    def __init__(self):
        self.settings = get_settings()
        self.notification_log_buffer = deque()
        self.system_log_buffer = deque()
        self.last_flush = datetime.utcnow()
        
    async def process_notification_log(self, message_data: Dict[str, Any]) -> bool:
        """
        Process a notification log message
        
        Args:
            message_data: Message data from RabbitMQ
            
        Returns:
            bool: Success status
        """
        try:
            # Validate and parse the log message
            log_message = NotificationLogMessage(**message_data)
            
            # Add to buffer for batch processing
            log_data = {
                'id': str(uuid.uuid4()),
                'notification_id': log_message.notification_id,
                'user_id': log_message.user_id,
                'notification_type': log_message.notification_type,
                'status': log_message.status,
                'provider': log_message.provider,
                'subject': log_message.subject,
                'sent_at': log_message.sent_at,
                'delivered_at': log_message.delivered_at,
                'provider_message_id': log_message.provider_message_id,
                'error_message': log_message.error_message,
                'retry_count': log_message.retry_count,
                'metadata': log_message.metadata,
                'created_at': log_message.created_at
            }
            
            self.notification_log_buffer.append(log_data)
            
            # Check if we should flush the buffer
            await self._check_and_flush_buffers()
            
            logger.debug(f"Processed notification log: {log_message.notification_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing notification log: {str(e)}")
            return False
            
    async def process_system_log(self, message_data: Dict[str, Any]) -> bool:
        """
        Process a system log message
        
        Args:
            message_data: Message data from RabbitMQ
            
        Returns:
            bool: Success status
        """
        try:
            # Validate and parse the log message
            log_message = SystemLogMessage(**message_data)
            
            # Add to buffer for batch processing
            log_data = {
                'id': str(uuid.uuid4()),
                'service_name': log_message.service_name,
                'level': log_message.level,
                'message': log_message.message,
                'correlation_id': log_message.correlation_id,
                'user_id': log_message.user_id,
                'metadata': log_message.metadata,
                'timestamp': log_message.timestamp
            }
            
            self.system_log_buffer.append(log_data)
            
            # Check if we should flush the buffer
            await self._check_and_flush_buffers()
            
            logger.debug(f"Processed system log from {log_message.service_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing system log: {str(e)}")
            return False
            
    async def _check_and_flush_buffers(self):
        """Check if buffers should be flushed and flush if necessary"""
        now = datetime.utcnow()
        time_since_last_flush = (now - self.last_flush).total_seconds()
        
        # Flush if buffer is full or enough time has passed
        should_flush = (
            len(self.notification_log_buffer) >= self.settings.BATCH_SIZE or
            len(self.system_log_buffer) >= self.settings.BATCH_SIZE or
            time_since_last_flush >= self.settings.FLUSH_INTERVAL
        )
        
        if should_flush:
            await self._flush_buffers()
            
    async def _flush_buffers(self):
        """Flush all buffered logs to the database"""
        try:
            # Flush notification logs
            if self.notification_log_buffer:
                notification_logs = list(self.notification_log_buffer)
                self.notification_log_buffer.clear()
                
                # Process logs in batches
                for log_data in notification_logs:
                    await db_client.log_notification_event(log_data)
                    
                logger.info(f"Flushed {len(notification_logs)} notification logs")
            
            # Flush system logs
            if self.system_log_buffer:
                system_logs = list(self.system_log_buffer)
                self.system_log_buffer.clear()
                
                # Process logs in batches
                for log_data in system_logs:
                    await db_client.log_system_event(log_data)
                    
                logger.info(f"Flushed {len(system_logs)} system logs")
                
            # Update last flush time
            self.last_flush = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Error flushing log buffers: {str(e)}")
            
    async def aggregate_daily_logs(self):
        """Aggregate logs for the previous day"""
        try:
            # Get yesterday's date
            yesterday = datetime.utcnow() - timedelta(days=1)
            
            # Aggregate logs
            success = await db_client.aggregate_logs(yesterday)
            
            if success:
                logger.info(f"Successfully aggregated logs for {yesterday.date()}")
            else:
                logger.error(f"Failed to aggregate logs for {yesterday.date()}")
                
        except Exception as e:
            logger.error(f"Error aggregating daily logs: {str(e)}")
            
    async def cleanup_old_logs(self):
        """Clean up old logs based on retention policy"""
        try:
            success = await db_client.cleanup_old_logs()
            
            if success:
                logger.info("Successfully cleaned up old logs")
            else:
                logger.error("Failed to clean up old logs")
                
        except Exception as e:
            logger.error(f"Error cleaning up old logs: {str(e)}")
            
    async def force_flush(self):
        """Force flush all buffered logs"""
        await self._flush_buffers()
        

# Singleton instance
logging_service = LoggingService()