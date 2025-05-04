import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time

from app.api.endpoints import router as api_router
from app.core.config import get_settings
from app.core.rabbitmq import rabbitmq_client
from app.db.redis_client import redis_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.DESCRIPTION,
    version=settings.VERSION,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add middleware for request logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log request information and timing"""
    start_time = time.time()
    
    # Process request
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Log request details
        logger.info(
            f"{request.method} {request.url.path} "
            f"completed in {process_time:.3f}s with status {response.status_code}"
        )
        
        # Add processing time header
        response.headers["X-Process-Time"] = f"{process_time:.3f}s"
        return response
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(
            f"{request.method} {request.url.path} "
            f"failed after {process_time:.3f}s: {str(e)}"
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )

# Include routers
app.include_router(api_router, prefix=settings.API_PREFIX)

@app.on_event("startup")
async def startup_event():
    """Initialize connections on startup"""
    logger.info("Starting notification orchestrator service")
    
    # Connect to RabbitMQ
    await rabbitmq_client.connect()
    
    # Connect to Redis
    await redis_client.connect()
    
    logger.info("Notification orchestrator service started")

@app.on_event("shutdown")
async def shutdown_event():
    """Close connections on shutdown"""
    logger.info("Shutting down notification orchestrator service")
    
    # Close RabbitMQ connection
    await rabbitmq_client.close()
    
    # Close Redis connection
    await redis_client.close()
    
    logger.info("Notification orchestrator service shut down")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "running"
    }

# Run the application with Uvicorn if executed directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )