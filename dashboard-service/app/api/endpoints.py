from fastapi import APIRouter, HTTPException, Depends, Path, Query
from fastapi.responses import JSONResponse
from typing import Optional
from datetime import datetime, date

from app.models.dashboard import (
    NotificationType,
    NotificationStatus,
    TimeRange,
    NotificationLogsResponse,
    NotificationDetailResponse,
    StatsResponse
)
from app.services.dashboard_service import dashboard_service
from app.core.config import get_settings

router = APIRouter()
settings = get_settings()


@router.get("/logs", response_model=NotificationLogsResponse)
async def get_logs(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE, description="Items per page"),
    notification_type: Optional[NotificationType] = Query(None, description="Filter by notification type"),
    status: Optional[NotificationStatus] = Query(None, description="Filter by status"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date")
):
    """
    Get notification logs with pagination and filtering
    """
    try:
        response = await dashboard_service.get_notification_logs(
            page=page,
            page_size=page_size,
            notification_type=notification_type,
            status=status,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs/{notification_id}", response_model=NotificationDetailResponse)
async def get_notification_detail(
    notification_id: str = Path(..., description="Notification ID")
):
    """
    Get detailed information about a specific notification
    """
    try:
        response = await dashboard_service.get_notification_detail(notification_id)
        if not response.logs:
            raise HTTPException(status_code=404, detail="Notification not found")
        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    time_range: TimeRange = Query(..., description="Time range for statistics"),
    start_date: Optional[date] = Query(None, description="Start date for custom range"),
    end_date: Optional[date] = Query(None, description="End date for custom range")
):
    """
    Get notification statistics for a time range
    """
    try:
        response = await dashboard_service.get_stats(
            time_range=time_range,
            start_date=start_date,
            end_date=end_date
        )
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))