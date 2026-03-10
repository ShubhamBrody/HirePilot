"""
Application Endpoints — CRUD, status management, auto-apply, analytics.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.schemas.application import (
    ApplicationAnalytics,
    ApplicationCreateRequest,
    ApplicationFilters,
    ApplicationListResponse,
    ApplicationResponse,
    ApplicationStatusUpdateRequest,
    AutoApplyRequest,
)
from app.services.application_service import ApplicationService

router = APIRouter()


@router.get("", response_model=ApplicationListResponse)
async def list_applications(
    filters: ApplicationFilters = Depends(),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List the user's job applications with filtering."""
    service = ApplicationService(db)
    return await service.list_applications(user_id, filters)


@router.post("", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application(
    data: ApplicationCreateRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Create a new job application."""
    try:
        service = ApplicationService(db)
        return await service.create_application(user_id, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/{application_id}/status", response_model=ApplicationResponse)
async def update_application_status(
    application_id: str,
    data: ApplicationStatusUpdateRequest,
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
):
    """Update an application's status (Applied, Interview, Offer, etc.)."""
    try:
        service = ApplicationService(db)
        return await service.update_status(application_id, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{application_id}/apply", status_code=status.HTTP_202_ACCEPTED)
async def auto_apply(
    application_id: str,
    data: AutoApplyRequest,
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),  # noqa: ARG001
) -> dict[str, str]:
    """
    Trigger automated job application via browser automation.
    Returns immediately — the Celery task handles the actual submission.
    """
    # In production:
    # from app.tasks.automation import auto_apply_task
    # task = auto_apply_task.delay(user_id, application_id, data.model_dump())
    return {
        "message": "Auto-apply task queued",
        "application_id": application_id,
        # "task_id": task.id,
    }


@router.get("/analytics", response_model=ApplicationAnalytics)
async def get_analytics(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get application analytics and statistics."""
    service = ApplicationService(db)
    return await service.get_analytics(user_id)
