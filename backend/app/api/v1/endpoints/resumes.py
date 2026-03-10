"""
Resume Endpoints — CRUD, compilation, tailoring, templates.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.repositories.resume_repo import ResumeTemplateRepository
from app.schemas.resume import (
    ResumeCompileResponse,
    ResumeListResponse,
    ResumeTemplateResponse,
    ResumeTailorRequest,
    ResumeTailorResponse,
    ResumeVersionCreateRequest,
    ResumeVersionResponse,
    ResumeVersionUpdateRequest,
)
from app.services.resume_service import ResumeService

router = APIRouter()


@router.get("", response_model=ResumeListResponse)
async def list_resumes(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List all resume versions for the current user."""
    service = ResumeService(db)
    return await service.list_versions(user_id)


@router.post("", response_model=ResumeVersionResponse, status_code=status.HTTP_201_CREATED)
async def create_resume(
    data: ResumeVersionCreateRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Create a new resume version."""
    service = ResumeService(db)
    return await service.create_version(user_id, data)


@router.get("/master", response_model=ResumeVersionResponse | None)
async def get_master_resume(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get the user's master resume."""
    service = ResumeService(db)
    result = await service.get_master_resume(user_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No master resume found. Upload one first.",
        )
    return result


@router.get("/templates", response_model=list[ResumeTemplateResponse])
async def list_templates(db: AsyncSession = Depends(get_db)):
    """List available LaTeX resume templates."""
    repo = ResumeTemplateRepository(db)
    templates = await repo.get_active_templates()
    return [ResumeTemplateResponse.model_validate(t) for t in templates]


@router.get("/{resume_id}", response_model=ResumeVersionResponse)
async def get_resume(
    resume_id: str,
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
):
    """Get a specific resume version."""
    try:
        service = ResumeService(db)
        return await service.get_version(resume_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{resume_id}", response_model=ResumeVersionResponse)
async def update_resume(
    resume_id: str,
    data: ResumeVersionUpdateRequest,
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
):
    """Update a resume version."""
    try:
        service = ResumeService(db)
        return await service.update_version(resume_id, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume(
    resume_id: str,
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
):
    """Delete a resume version."""
    try:
        service = ResumeService(db)
        await service.delete_version(resume_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{resume_id}/compile", response_model=ResumeCompileResponse)
async def compile_resume(
    resume_id: str,
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
):
    """Trigger LaTeX-to-PDF compilation for a resume version."""
    try:
        service = ResumeService(db)
        return await service.compile_resume(resume_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/tailor", response_model=ResumeTailorResponse, status_code=status.HTTP_202_ACCEPTED)
async def tailor_resume(
    data: ResumeTailorRequest,
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),  # noqa: ARG001
):
    """
    AI-tailor a resume for a specific job description.
    Returns a new resume version optimized for ATS.
    In production: dispatches Celery AI task.
    """
    # In production:
    # from app.tasks.ai_tasks import tailor_resume_task
    # task = tailor_resume_task.delay(user_id, data.model_dump())
    return ResumeTailorResponse(
        resume_version_id="pending",
        name=f"Tailored for job {data.job_listing_id}",
        changes_summary="AI tailoring task queued",
        matched_keywords=[],
        optimization_score=0.0,
    )
