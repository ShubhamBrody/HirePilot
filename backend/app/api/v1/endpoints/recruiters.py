"""
Recruiter Endpoints — Discovery, outreach, messaging.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.recruiter import ConnectionStatus, OutreachStatus
from app.repositories.recruiter_repo import OutreachMessageRepository, RecruiterRepository
from app.schemas.recruiter import (
    GenerateMessageRequest,
    GenerateMessageResponse,
    OutreachMessageRequest,
    OutreachMessageResponse,
    RecruiterListResponse,
    RecruiterResponse,
)

router = APIRouter()


@router.get("", response_model=RecruiterListResponse)
async def list_recruiters(
    connection_status: ConnectionStatus | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List discovered recruiters."""
    repo = RecruiterRepository(db)
    skip = (page - 1) * page_size
    recruiters = await repo.get_user_recruiters(
        uuid.UUID(user_id), skip=skip, limit=page_size, connection_status=connection_status
    )
    return RecruiterListResponse(
        recruiters=[RecruiterResponse.model_validate(r) for r in recruiters],
        total=len(recruiters),
    )


@router.get("/{recruiter_id}", response_model=RecruiterResponse)
async def get_recruiter(
    recruiter_id: str,
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
):
    """Get a specific recruiter."""
    repo = RecruiterRepository(db)
    recruiter = await repo.get_by_id(uuid.UUID(recruiter_id))
    if not recruiter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recruiter not found")
    return RecruiterResponse.model_validate(recruiter)


@router.post("/{recruiter_id}/outreach", response_model=OutreachMessageResponse, status_code=status.HTTP_201_CREATED)
async def send_outreach(
    recruiter_id: str,
    data: OutreachMessageRequest,
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),  # noqa: ARG001
):
    """
    Send an outreach message to a recruiter.
    In production: dispatches via Celery with rate limiting.
    """
    # In production:
    # from app.tasks.outreach import send_outreach_task
    # task = send_outreach_task.delay(user_id, recruiter_id, data.model_dump())
    return OutreachMessageResponse(
        id="pending",
        recruiter_id=recruiter_id,
        message_type=data.message_type,
        subject=None,
        body=data.custom_message or "AI-generated message pending",
        ai_generated=data.custom_message is None,
        status=OutreachStatus.PENDING,
        sent_at=None,
        error_message=None,
        created_at=datetime.now(UTC),
    )


@router.get("/{recruiter_id}/messages", response_model=list[OutreachMessageResponse])
async def get_messages(
    recruiter_id: str,
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
):
    """Get all outreach messages sent to a recruiter."""
    repo = OutreachMessageRepository(db)
    messages = await repo.get_messages_for_recruiter(uuid.UUID(recruiter_id))
    return [OutreachMessageResponse.model_validate(m) for m in messages]


@router.post("/generate-message", response_model=GenerateMessageResponse)
async def generate_message(
    data: GenerateMessageRequest,
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
):
    """
    Preview an AI-generated outreach message without sending it.
    """
    repo = RecruiterRepository(db)
    recruiter = await repo.get_by_id(uuid.UUID(data.recruiter_id))
    if not recruiter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recruiter not found")

    # In production: call AI service
    # from app.services.ai_service import AIService
    # message = await AIService().generate_outreach_message(user_id, recruiter, data)

    return GenerateMessageResponse(
        suggested_message=f"Hi {recruiter.name},\n\nI noticed your team is hiring and I'd love to connect. My background in backend engineering aligns well with the role.\n\nBest regards",
        recruiter_name=recruiter.name,
        company=recruiter.company,
        job_title=recruiter.title,
    )
