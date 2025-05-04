from fastapi import APIRouter, HTTPException, Depends, Path, Query
from fastapi.responses import JSONResponse

from app.models.preferences import (
    UserPreferences,
    PreferenceUpdateRequest,
    PreferenceResponse,
    NotificationChannel,
    NotificationCategory
)
from app.services.preferences_service import preferences_service

router = APIRouter()


@router.get("/preferences/{user_id}", response_model=PreferenceResponse)
async def get_preferences(user_id: str = Path(..., description="User ID")):
    """
    Get user notification preferences
    """
    try:
        preferences, message = await preferences_service.get_user_preferences(user_id)
        if not preferences:
            raise HTTPException(status_code=404, detail="User preferences not found")
            
        return PreferenceResponse(
            user_id=user_id,
            preferences=preferences,
            message=message
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/preferences/{user_id}", response_model=PreferenceResponse)
async def update_preferences(
    update_request: PreferenceUpdateRequest,
    user_id: str = Path(..., description="User ID")
):
    """
    Update user notification preferences
    """
    try:
        preferences, message = await preferences_service.update_user_preferences(user_id, update_request)
        if not preferences:
            raise HTTPException(status_code=404, detail="Failed to update user preferences")
            
        return PreferenceResponse(
            user_id=user_id,
            preferences=preferences,
            message=message
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/preferences/{user_id}")
async def delete_preferences(user_id: str = Path(..., description="User ID")):
    """
    Delete user notification preferences
    """
    try:
        success, message = await preferences_service.delete_user_preferences(user_id)
        if not success:
            raise HTTPException(status_code=404, detail="Failed to delete user preferences")
            
        return JSONResponse(
            status_code=200,
            content={"message": message}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/preferences/{user_id}/check")
async def check_notification_allowed(
    user_id: str = Path(..., description="User ID"),
    channel: NotificationChannel = Query(..., description="Notification channel"),
    category: NotificationCategory = Query(..., description="Notification category"),
    is_urgent: bool = Query(False, description="Is this an urgent notification?")
):
    """
    Check if a notification is allowed based on user preferences
    """
    try:
        allowed = await preferences_service.is_notification_allowed(
            user_id=user_id,
            channel=channel,
            category=category,
            is_urgent=is_urgent
        )
        
        return JSONResponse(
            status_code=200,
            content={
                "allowed": allowed,
                "user_id": user_id,
                "channel": channel,
                "category": category,
                "is_urgent": is_urgent
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))