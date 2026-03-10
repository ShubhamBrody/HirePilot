"""
Job Endpoints — Discovery, listing, match scoring.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.job import JobSource
from app.repositories.job_repo import JobRepository
from app.schemas.job import (
    JobListingListResponse,
    JobListingResponse,
    JobMatchScoreResponse,
    TriggerJobSearchRequest,
)

router = APIRouter()


@router.get("", response_model=JobListingListResponse)
async def list_jobs(
    source: JobSource | None = None,
    company: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List discovered jobs for the current user."""
    repo = JobRepository(db)
    skip = (page - 1) * page_size
    jobs = await repo.get_user_jobs(
        uuid.UUID(user_id), skip=skip, limit=page_size, source=source, company=company
    )
    total = await repo.count_user_jobs(uuid.UUID(user_id))
    return JobListingListResponse(
        jobs=[JobListingResponse.model_validate(j) for j in jobs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/top-matches", response_model=list[JobListingResponse])
async def top_matches(
    min_score: float = Query(0.5, ge=0.0, le=1.0),
    limit: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get top jobs ranked by AI match score."""
    repo = JobRepository(db)
    jobs = await repo.get_jobs_by_match_score(
        uuid.UUID(user_id), min_score=min_score, limit=limit
    )
    return [JobListingResponse.model_validate(j) for j in jobs]


@router.get("/{job_id}", response_model=JobListingResponse)
async def get_job(
    job_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific job listing."""
    repo = JobRepository(db)
    job = await repo.get_by_id(uuid.UUID(job_id))
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return JobListingResponse.model_validate(job)


@router.post("/search", status_code=status.HTTP_202_ACCEPTED)
async def trigger_job_search(
    data: TriggerJobSearchRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),  # noqa: ARG001
):
    """
    Trigger an async job search across configured sources.
    Returns immediately — results are delivered via the jobs list endpoint.
    """
    # In production: dispatch Celery task
    # from app.tasks.scraping import scrape_jobs_task
    # task = scrape_jobs_task.delay(user_id, data.model_dump())
    return {
        "message": "Job search initiated",
        "filters": data.filters.model_dump(),
        "sources": [s.value for s in data.sources],
        # "task_id": task.id,
    }


@router.get("/{job_id}/match-score", response_model=JobMatchScoreResponse)
async def get_match_score(
    job_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Get AI-computed match score for a job relative to the user's profile.
    """
    repo = JobRepository(db)
    job = await repo.get_by_id(uuid.UUID(job_id))
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    # In production: call AI service for real scoring
    # from app.services.ai_service import AIService
    # score = await AIService().compute_match_score(user_id, job)

    return JobMatchScoreResponse(
        job_id=str(job.id),
        match_score=job.match_score or 0.0,
        reasoning=job.match_reasoning or "Score not yet computed",
        matched_skills=[],
        missing_skills=[],
        recommendations=["Run AI scoring to get detailed analysis"],
    )
