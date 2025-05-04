from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Dict, Any

from app.models.notification import (
    NotificationRequest,
    NotificationResponse,
    BulkNotificationRequest,
    BulkNotificationResponse
)
from app.services.notification_service import notification_service
from app.core.rabbitmq import rabbitmq_client
from app.db.redis_client import redis_client

router = APIRouter()


@router.post("/notifications", response_model=NotificationResponse)
async def send_notification(request: NotificationRequest):
    """
    Send a notification to a user
    """
    try:
        response = await notification_service.send_notification(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/notifications/bulk", response_model=BulkNotificationResponse)
async def send_bulk_notifications(request: BulkNotificationRequest):
    """
    Send multiple notifications in a single request
    """
    try:
        response = await notification_service.send_bulk_notifications(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    health_status = {
        "status": "healthy",
        "services": {
            "api": "up",
            "rabbitmq": "unknown",
            "redis": "unknown"
        }
    }
    
    # Check RabbitMQ connection
    try:
        if not rabbitmq_client.connection or rabbitmq_client.connection.is_closed:
            await rabbitmq_client.connect()
        health_status["services"]["rabbitmq"] = "up"
    except Exception as e:
        health_status["services"]["rabbitmq"] = "down"
        health_status["status"] = "degraded"
    
    # Check Redis connection
    try:
        if not redis_client.redis_client:
            await redis_client.connect()
        await redis_client.redis_client.ping()
        health_status["services"]["redis"] = "up"
    except Exception as e:
        health_status["services"]["redis"] = "down"
        health_status["status"] = "degraded"
    
    # Set appropriate status code
    status_code = 200 if health_status["status"] == "healthy" else 503
    
    return JSONResponse(
        status_code=status_code,
        content=health_status
    )