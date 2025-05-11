import json
import logging
from typing import Dict, Any, Optional, Callable, Awaitable
import aio_pika
from aio_pika import ExchangeType, Message, IncomingMessage
from app.core.settings import get_settings

logger = logging.getLogger(__name__)


class RabbitMQClient:
    def __init__(self):
        self.settings = get_settings()
        self.connection = None
        self.channel = None
        self.exchange = None
        self.dlx_exchange = None
        self.message_handler = None
    
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
            
            logger.info("Successfully connected to RabbitMQ")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {str(e)}")
            raise
            
    async def setup_consumer(self, message_handler: Callable[[Dict[str, Any], Dict[str, Any]], Awaitable[bool]]):
        """
        Set up a consumer for the push notification queue
        
        Args:
            message_handler: Async function to handle incoming messages.
                             Should return True if message was processed successfully, False otherwise.
        """
        if not self.channel:
            await self.connect()
            
        self.message_handler = message_handler
        
        # Declare the main queue with dead-letter configuration
        queue_args = {
            "x-dead-letter-exchange": self.settings.DLX_EXCHANGE,
            "x-dead-letter-routing-key": "notification.push.failed"
        }
        
        # Declare push queue
        push_queue = await self.channel.declare_queue(
            self.settings.PUSH_QUEUE,
            durable=True,
            arguments=queue_args
        )
        
        # Bind queue to exchange
        await push_queue.bind(
            self.exchange,
            routing_key="notification.push"
        )
        
        # Declare DLQ for failed messages
        dlq_queue = await self.channel.declare_queue(
            self.settings.DLQ_QUEUE,
            durable=True
        )
        
        # Bind DLQ to DLX
        await dlq_queue.bind(
            self.dlx_exchange,
            routing_key="notification.push.failed"
        )
        
        # Start consuming messages
        await push_queue.consume(self._on_message)
        
        logger.info(f"Started consuming from queue: {self.settings.PUSH_QUEUE}")
        
    async def _on_message(self, message: IncomingMessage):
        """
        Process incoming messages
        
        Args:
            message: IncomingMessage from RabbitMQ
        """
        async with message.process():
            try:
                # Decode message body
                body = message.body.decode()
                message_data = json.loads(body)
                
                # Extract headers
                headers = message.headers or {}
                
                logger.info(f"Received message: {message.message_id}")
                
                if self.message_handler:
                    # Process message with handler
                    success = await self.message_handler(message_data, headers)
                    
                    if not success:
                        # If processing failed, handle retry logic
                        await self._handle_retry(message_data, headers)
                else:
                    logger.warning("No message handler registered")
                    
            except json.JSONDecodeError:
                logger.error("Failed to decode message JSON")
            except Exception as e:
                logger.exception(f"Error processing message: {str(e)}")
                
    async def _handle_retry(self, message_data: Dict[str, Any], headers: Dict[str, Any]):
        """
        Handle retry logic for failed messages
        
        Args:
            message_data: The message payload
            headers: Message headers containing retry information
        """
        # Get retry count from headers
        retry_count = headers.get("retry_count", 0)
        max_retries = headers.get("max_retries", self.settings.MAX_RETRIES)
        
        if retry_count < max_retries:
            # Increment retry count
            retry_count += 1
            
            # Calculate delay with exponential backoff
            delay = self.settings.RETRY_DELAY * (self.settings.RETRY_BACKOFF_FACTOR ** (retry_count - 1))
            
            logger.info(f"Scheduling retry {retry_count}/{max_retries} with delay {delay}s")
            
            # Update headers with new retry count
            new_headers = headers.copy()
            new_headers["retry_count"] = retry_count
            
            # Create a new message
            message = Message(
                body=json.dumps(message_data).encode(),
                content_type="application/json",
                headers=new_headers,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            )
            
            # Publish to the exchange with delay
            # Note: This requires RabbitMQ delayed message exchange plugin
            # or you can implement a delay queue pattern if the plugin is not available
            await self.exchange.publish(
                message=message,
                routing_key="notification.push",
                expiration=int(delay * 1000)  # Convert to milliseconds
            )
        else:
            logger.warning(f"Maximum retries reached, sending to DLQ: {message_data.get('notification_id')}")
            
            # Create a new message for the DLQ
            message = Message(
                body=json.dumps(message_data).encode(),
                content_type="application/json",
                headers=headers,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            )
            
            # Publish to the DLX
            await self.dlx_exchange.publish(
                message=message,
                routing_key="notification.push.failed"
            )
            
    async def close(self):
        """Close the RabbitMQ connection"""
        if self.connection:
            await self.connection.close()
            logger.info("RabbitMQ connection closed")


# Singleton instance
rabbitmq_client = RabbitMQClient()