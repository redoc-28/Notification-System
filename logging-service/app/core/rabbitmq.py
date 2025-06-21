import json
import logging
from typing import Dict, Any, Optional, Callable, Awaitable
import aio_pika
from aio_pika import ExchangeType, Message, IncomingMessage
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class RabbitMQClient:
    def __init__(self):
        self.settings = get_settings()
        self.connection = None
        self.channel = None
        self.exchange = None
        self.dlx_exchange = None
        self.message_handlers = {}
    
    async def connect(self):
        """Establish connection to RabbitMQ"""
        try:
            # Create connection
            self.connection = await aio_pika.connect_robust(
                self.settings.get_amqp_url()
            )
            
            # Create channel
            self.channel = await self.connection.channel()
            await self.channel.set_qos(prefetch_count=20)
            
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
            
    async def setup_consumers(self, 
                             notification_log_handler: Callable[[Dict[str, Any]], Awaitable[bool]],
                             system_log_handler: Optional[Callable[[Dict[str, Any]], Awaitable[bool]]] = None):
        """
        Set up consumers for logging queues
        
        Args:
            notification_log_handler: Handler for notification log messages
            system_log_handler: Handler for system log messages (optional)
        """
        if not self.channel:
            await self.connect()
            
        self.message_handlers['notification_logs'] = notification_log_handler
        if system_log_handler:
            self.message_handlers['system_logs'] = system_log_handler
        
        # Set up notification logs queue
        await self._setup_notification_logs_queue()
        
        # Set up system logs queue if handler is provided
        if system_log_handler:
            await self._setup_system_logs_queue()
        
    async def _setup_notification_logs_queue(self):
        """Set up notification logs queue"""
        # Declare the main queue with dead-letter configuration
        queue_args = {
            "x-dead-letter-exchange": self.settings.DLX_EXCHANGE,
            "x-dead-letter-routing-key": "logs.notification.failed"
        }
        
        # Declare notification logs queue
        logs_queue = await self.channel.declare_queue(
            self.settings.LOGGING_QUEUE,
            durable=True,
            arguments=queue_args
        )
        
        # Bind queue to exchange for different routing keys
        routing_keys = [
            "logs.notification.email",
            "logs.notification.sms", 
            "logs.notification.push",
            "logs.notification.*"
        ]
        
        for routing_key in routing_keys:
            await logs_queue.bind(self.exchange, routing_key=routing_key)
        
        # Start consuming messages
        await logs_queue.consume(self._on_notification_log_message)
        
        logger.info(f"Started consuming notification logs from queue: {self.settings.LOGGING_QUEUE}")
        
    async def _setup_system_logs_queue(self):
        """Set up system logs queue"""
        # Declare system logs queue
        system_logs_queue = await self.channel.declare_queue(
            self.settings.SYSTEM_LOGS_QUEUE,
            durable=True
        )
        
        # Bind queue to exchange
        await system_logs_queue.bind(self.exchange, routing_key="logs.system.*")
        
        # Start consuming messages
        await system_logs_queue.consume(self._on_system_log_message)
        
        logger.info(f"Started consuming system logs from queue: {self.settings.SYSTEM_LOGS_QUEUE}")
        
    async def _on_notification_log_message(self, message: IncomingMessage):
        """
        Process incoming notification log messages
        
        Args:
            message: IncomingMessage from RabbitMQ
        """
        async with message.process():
            try:
                # Decode message body
                body = message.body.decode()
                message_data = json.loads(body)
                
                logger.debug(f"Received notification log message: {message.message_id}")
                
                handler = self.message_handlers.get('notification_logs')
                if handler:
                    success = await handler(message_data)
                    if not success:
                        logger.error(f"Failed to process notification log message: {message.message_id}")
                else:
                    logger.warning("No notification log handler registered")
                    
            except json.JSONDecodeError:
                logger.error("Failed to decode notification log message JSON")
            except Exception as e:
                logger.exception(f"Error processing notification log message: {str(e)}")
                
    async def _on_system_log_message(self, message: IncomingMessage):
        """
        Process incoming system log messages
        
        Args:
            message: IncomingMessage from RabbitMQ
        """
        async with message.process():
            try:
                # Decode message body
                body = message.body.decode()
                message_data = json.loads(body)
                
                logger.debug(f"Received system log message: {message.message_id}")
                
                handler = self.message_handlers.get('system_logs')
                if handler:
                    success = await handler(message_data)
                    if not success:
                        logger.error(f"Failed to process system log message: {message.message_id}")
                else:
                    logger.warning("No system log handler registered")
                    
            except json.JSONDecodeError:
                logger.error("Failed to decode system log message JSON")
            except Exception as e:
                logger.exception(f"Error processing system log message: {str(e)}")
            
    async def close(self):
        """Close the RabbitMQ connection"""
        if self.connection:
            await self.connection.close()
            logger.info("RabbitMQ connection closed")


# Singleton instance
rabbitmq_client = RabbitMQClient()