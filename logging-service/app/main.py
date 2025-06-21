import logging
import asyncio
import signal
import sys
from datetime import datetime, time

from app.core.config import get_settings
from app.core.rabbitmq import rabbitmq_client
from app.db.database import init_db
from app.services.logging_service import logging_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

# Global flag for graceful shutdown
shutdown_flag = False

# Signal handler for graceful shutdown
async def shutdown(signal, loop):
    """Gracefully shut down the service"""
    global shutdown_flag
    logger.info(f"Received exit signal {signal.name}...")
    shutdown_flag = True
    
    # Force flush any remaining logs
    await logging_service.force_flush()
    
    # Close RabbitMQ connection
    await rabbitmq_client.close()
    
    logger.info("Shutdown complete")


async def daily_maintenance_task():
    """Daily maintenance task for log aggregation and cleanup"""
    while not shutdown_flag:
        try:
            now = datetime.now()
            
            # Run maintenance at 2 AM daily
            if now.hour == 2 and now.minute < 5:
                logger.info("Starting daily maintenance tasks")
                
                # Aggregate logs for the previous day
                await logging_service.aggregate_daily_logs()
                
                # Clean up old logs based on retention policy
                await logging_service.cleanup_old_logs()
                
                logger.info("Daily maintenance tasks completed")
                
                # Sleep for 5 minutes to avoid running multiple times
                await asyncio.sleep(300)
            else:
                # Check every hour
                await asyncio.sleep(3600)
                
        except Exception as e:
            logger.error(f"Error in daily maintenance task: {str(e)}")
            await asyncio.sleep(3600)


async def periodic_flush_task():
    """Periodic task to flush log buffers"""
    while not shutdown_flag:
        try:
            await asyncio.sleep(settings.FLUSH_INTERVAL)
            await logging_service.force_flush()
        except Exception as e:
            logger.error(f"Error in periodic flush task: {str(e)}")


async def main():
    """Main entry point for the service"""
    try:
        # Initialize database
        await init_db()
        
        # Connect to RabbitMQ
        await rabbitmq_client.connect()
        
        # Set up consumers with our message handlers
        await rabbitmq_client.setup_consumers(
            notification_log_handler=logging_service.process_notification_log,
            system_log_handler=logging_service.process_system_log
        )
        
        logger.info("Logging service started")
        
        # Start background tasks
        daily_task = asyncio.create_task(daily_maintenance_task())
        flush_task = asyncio.create_task(periodic_flush_task())
        
        # Keep the service running
        while not shutdown_flag:
            await asyncio.sleep(1)
            
        # Cancel background tasks
        daily_task.cancel()
        flush_task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(daily_task, flush_task, return_exceptions=True)
        
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
        logger.info("Logging service shut down successfully")