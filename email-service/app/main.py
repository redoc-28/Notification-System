import logging
import asyncio
import signal
import sys

from app.core.config import get_settings
from app.core.rabbitmq import rabbitmq_client
from app.db.database import init_db
from app.services.email_service import email_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

# Signal handler for graceful shutdown
async def shutdown(signal, loop):
    """Gracefully shut down the service"""
    logger.info(f"Received exit signal {signal.name}...")
    
    # Close RabbitMQ connection
    await rabbitmq_client.close()
    
    # Stop the event loop
    loop.stop()
    
    logger.info("Shutdown complete")


async def main():
    """Main entry point for the service"""
    try:
        # Initialize database
        await init_db()
        
        # Connect to RabbitMQ
        await rabbitmq_client.connect()
        
        # Set up consumer with our message handler
        await rabbitmq_client.setup_consumer(email_service.process_email)
        
        logger.info(f"Email service started (Provider: {settings.EMAIL_PROVIDER})")
        
        # Keep the service running
        while True:
            await asyncio.sleep(3600)  # Sleep for an hour (or any long duration)
            
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    # Get the event loop
    loop = asyncio.get_event_loop()
    
    # Register signal handlers for graceful shutdown
    for s in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            s, lambda s=s: asyncio.create_task(shutdown(s, loop))
        )
    
    try:
        # Run the main function
        loop.run_until_complete(main())
    finally:
        # Close the event loop
        loop.close()
        logger.info("Service shut down successfully")