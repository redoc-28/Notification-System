import json
import logging
from typing import Dict, Any, Optional
import aio_pika
from aio_pika import ExchangeType, Message
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class RabbitMQClient:
    def __init__(self):
        self.settings = get_settings()
        self.connection = None
        self.channel = None
        self.exchange = None
        self.dlx_exchange = None

    async def connect(self):
        """Establish connection to RabbitMQ"""
        try:
            # Create connection
            self.connection = await aio_pika.connect_robust(
                self.settings.get_amqp_url()
            )
            
            # Create channel
            self.channel = await self.connection.channel()
            await self.channel.set_qos(prefetch_count=10)
            
            # Declare the main exchange
            self.exchange = await self.channel.declare_exchange(
                self.settings.EXCHANGE_NAME,
                ExchangeType.TOPIC,
                durable=True
            )
            
            # Declare the dead letter exchange for failed messages
            self.dlx_exchange = await self.channel.declare_exchange(
                self.settings.DLX_EXCHANGE,
                ExchangeType.TOPIC,
                durable=True
            )
            
            # Set up queues with dead-letter handling
            await self._setup_queues()
            
            logger.info("Successfully connected to RabbitMQ")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {str(e)}")
            raise

    async def _setup_queues(self):
        """Set up queues with proper bindings and dead-letter configuration"""
        # Common arguments for all queues
        queue_args = {
            "x-dead-letter-exchange": self.settings.DLX_EXCHANGE,
            "x-dead-letter-routing-key": "notification.email.failed"
        }
        
        # Declare email queue
        email_queue = await self.channel.declare_queue(
            self.settings.EMAIL_QUEUE,
            durable=True,
            arguments=queue_args
        )
        await email_queue.bind(self.exchange, routing_key="notification.email")
        
        # Declare email dead-letter queue
        email_dlq = await self.channel.declare_queue(
            f"{self.settings.EMAIL_QUEUE}.dlq",
            durable=True
        )
        await email_dlq.bind(self.dlx_exchange, routing_key="notification.email.failed")
        
        # Update queue args for SMS queue
        queue_args["x-dead-letter-routing-key"] = "notification.sms.failed"
        
        # Declare SMS queue
        sms_queue = await self.channel.declare_queue(
            self.settings.SMS_QUEUE,
            durable=True,
            arguments=queue_args
        )
        await sms_queue.bind(self.exchange, routing_key="notification.sms")
        
        # Declare SMS dead-letter queue
        sms_dlq = await self.channel.declare_queue(
            f"{self.settings.SMS_QUEUE}.dlq",
            durable=True
        )
        await sms_dlq.bind(self.dlx_exchange, routing_key="notification.sms.failed")
        
        # Update queue args for push queue
        queue_args["x-dead-letter-routing-key"] = "notification.push.failed"
        
        # Declare push notification queue
        push_queue = await self.channel.declare_queue(
            self.settings.PUSH_QUEUE,
            durable=True,
            arguments=queue_args
        )
        await push_queue.bind(self.exchange, routing_key="notification.push")
        
        # Declare push notification dead-letter queue
        push_dlq = await self.channel.declare_queue(
            f"{self.settings.PUSH_QUEUE}.dlq",
            durable=True
        )
        await push_dlq.bind(self.dlx_exchange, routing_key="notification.push.failed")

    async def publish_message(self, routing_key: str, message_data: Dict[str, Any], 
                             headers: Optional[Dict[str, Any]] = None, 
                             priority: int = 0):
        """
        Publish a message to RabbitMQ
        
        Args:
            routing_key: The routing key (e.g., 'notification.email')
            message_data: Dictionary with message data
            headers: Optional headers for the message
            priority: Message priority (0-9)
            
        Returns:
            bool: Success status
        """
        try:
            if not self.exchange:
                await self.connect()
                
            # Convert message data to JSON
            message_body = json.dumps(message_data).encode()
            
            # Create message with optional headers and properties
            message = Message(
                body=message_body,
                content_type="application/json",
                headers=headers or {},
                priority=priority,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            )
            
            # Publish message
            await self.exchange.publish(
                message=message,
                routing_key=routing_key
            )
            
            logger.info(f"Published message to {routing_key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish message: {str(e)}")
            return False

    async def close(self):
        """Close the RabbitMQ connection"""
        if self.connection:
            await self.connection.close()
            logger.info("RabbitMQ connection closed")


# Singleton instance
rabbitmq_client = RabbitMQClient()