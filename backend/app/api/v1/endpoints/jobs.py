"""
Job Endpoints — Discovery, listing, match scoring, URL scraping.
"""

import uuid
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger
from app.core.security import get_current_user_id
from app.models.job import JobListing, JobSource
from app.repositories.job_repo import JobRepository
from app.repositories.resume_repo import ResumeRepository
from app.repositories.user_repo import UserRepository
from app.schemas.job import (
    JobListingListResponse,
    JobListingResponse,
    JobMatchScoreResponse,
    ScrapeJobURLRequest,
    ScrapeJobURLResponse,
    TriggerJobSearchRequest,
)
from app.services.llm_service import LLMService

logger = get_logger(__name__)

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
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
):
    """Get a specific job listing."""
    repo = JobRepository(db)
    job = await repo.get_by_id(uuid.UUID(job_id))
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return JobListingResponse.model_validate(job)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: str,
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a job listing (moves to trash)."""
    repo = JobRepository(db)
    job = await repo.get_by_id(uuid.UUID(job_id))
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    await repo.soft_delete(job)
    await db.commit()


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
    from app.tasks.scraping import scrape_jobs

    # Extract keywords from filters for the Celery task
    keywords = data.filters.keywords or []
    if data.filters.role:
        keywords = [data.filters.role] + keywords
    location = data.filters.location
    sources = [s.value for s in data.sources]

    task = scrape_jobs.delay(user_id, keywords, location, sources)
    return {
        "message": "Job search initiated",
        "filters": data.filters.model_dump(),
        "sources": sources,
        "task_id": task.id,
    }


@router.post("/search-linkedin")
async def search_jobs_linkedin(
    data: TriggerJobSearchRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Synchronous LinkedIn job search using authenticated Selenium session.
    Searches LinkedIn, saves results to DB, and returns them immediately.
    """
    from app.agents.linkedin_helper import linkedin_search_jobs

    keywords = data.filters.role or ""
    if data.filters.keywords:
        keywords += " " + " ".join(data.filters.keywords)
    keywords = keywords.strip()
    if not keywords:
        raise HTTPException(status_code=400, detail="Provide a role or keywords to search")

    location = data.filters.location or ""
    max_results = data.filters.max_results or 25

    try:
        li_result = await linkedin_search_jobs(db, user_id, keywords, location, max_results)
    except Exception as e:
        logger.error("LinkedIn job search failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"LinkedIn search error: {e}")

    if not li_result.get("success"):
        error_msg = li_result.get("error", "LinkedIn search failed")
        challenge = li_result.get("challenge", False)
        if challenge:
            return {
                "message": error_msg,
                "challenge": True,
                "jobs": [],
                "saved": 0,
                "source": "linkedin",
            }
        raise HTTPException(status_code=502, detail=error_msg)

    # Filter jobs by relevance using candidate profile
    raw_jobs = li_result.get("jobs", [])
    if raw_jobs:
        try:
            user_repo = UserRepository(db)
            user = await user_repo.get_by_id(uuid.UUID(user_id))
            candidate_yoe = getattr(user, "years_of_experience", None) if user else None
            candidate_level = getattr(user, "experience_level", None) if user else None

            resume_repo_filter = ResumeRepository(db)
            master = await resume_repo_filter.get_master_resume(uuid.UUID(user_id))
            resume_summary = master.latex_source[:800] if master else None

            llm = LLMService()
            suitable_indices = await llm.filter_jobs_by_relevance(
                raw_jobs,
                candidate_yoe=candidate_yoe,
                candidate_level=candidate_level,
                resume_summary=resume_summary,
            )
            filtered_count = len(raw_jobs) - len(suitable_indices)
            raw_jobs = [raw_jobs[i] for i in suitable_indices]
            if filtered_count > 0:
                logger.info("Filtered irrelevant jobs", removed=filtered_count, kept=len(raw_jobs))
        except Exception as e:
            logger.warning("Job relevance filtering skipped", error=str(e))

    # Save jobs to DB
    repo = JobRepository(db)
    saved_count = 0
    saved_jobs = []
    for raw in raw_jobs:
        source_url = raw.get("source_url", "")
        if not source_url:
            continue

        # Deduplicate
        existing = await repo.get_by_source_url(source_url)
        if existing:
            saved_jobs.append(existing)
            continue

        job = JobListing(
            id=uuid.uuid4(),
            user_id=uuid.UUID(user_id),
            title=raw.get("title", "Unknown"),
            company=raw.get("company", "Unknown"),
            location=raw.get("location"),
            description=raw.get("description") or f"{raw.get('title', 'Job')} at {raw.get('company', 'Company')} — scraped from LinkedIn",
            source=JobSource.LINKEDIN,
            source_url=source_url,
            source_job_id=raw.get("source_job_id"),
            discovered_at=datetime.now(UTC),
            is_active=True,
        )
        created = await repo.create(job)
        saved_jobs.append(created)
        saved_count += 1

    await db.commit()

    return {
        "message": f"Found {len(li_result.get('jobs', []))} jobs on LinkedIn, saved {saved_count} new",
        "jobs": [JobListingResponse.model_validate(j) for j in saved_jobs],
        "saved": saved_count,
        "total_found": li_result.get("total_found", 0),
        "source": "linkedin",
    }


@router.get("/{job_id}/match-score", response_model=JobMatchScoreResponse)
async def get_match_score(
    job_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Get AI-computed match score for a job relative to the user's master resume.
    Uses Ollama LLM for real-time analysis.
    """
    repo = JobRepository(db)
    job = await repo.get_by_id(uuid.UUID(job_id))
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    # Return pre-computed score if available
    if job.match_score is not None and job.match_score > 0:
        return JobMatchScoreResponse(
            job_id=str(job.id),
            match_score=job.match_score,
            reasoning=job.match_reasoning or "Pre-computed match score",
            matched_skills=[],
            missing_skills=[],
            strengths=[],
            weaknesses=[],
            recommendations=[],
        )

    # Get user's master resume for comparison
    resume_repo = ResumeRepository(db)
    master_resume = await resume_repo.get_master_resume(uuid.UUID(user_id))
    if not master_resume:
        return JobMatchScoreResponse(
            job_id=str(job.id),
            match_score=0.0,
            reasoning="No master resume found. Upload one to get fit analysis.",
            matched_skills=[],
            missing_skills=[],
            strengths=[],
            weaknesses=[],
            recommendations=["Upload a master resume to enable AI scoring"],
        )

    # Compute with Ollama
    llm = LLMService()
    result = await llm.compute_fit_score(
        resume_latex=master_resume.latex_source,
        job_description=job.description,
    )

    score = result.get("match_score", 0.0)
    reasoning = result.get("reasoning", "")

    # Persist to the job record
    job.match_score = score
    job.match_reasoning = reasoning
    await db.commit()

    return JobMatchScoreResponse(
        job_id=str(job.id),
        match_score=score,
        reasoning=reasoning,
        matched_skills=result.get("matched_skills", []),
        missing_skills=result.get("missing_skills", []),
        strengths=result.get("strengths", []),
        weaknesses=result.get("weaknesses", []),
        recommendations=result.get("recommendations", []),
    )


# ── Manual Job URL Scraping ─────────────────────────────────────


@router.post("/scrape-url", response_model=ScrapeJobURLResponse)
async def scrape_job_url(
    data: ScrapeJobURLRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Scrape a job URL, extract structured fields via AI, persist the listing,
    and optionally compute a fit score against a resume.
    """
    # Check if this URL already exists
    job_repo = JobRepository(db)
    existing = await job_repo.get_by_source_url(data.url)
    if existing:
        return ScrapeJobURLResponse(
            job=JobListingResponse.model_validate(existing),
            error=None,
        )

    # Fetch HTML from the URL
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(data.url, headers={"User-Agent": "HirePilot/1.0"})
            resp.raise_for_status()
            html_content = resp.text
    except httpx.HTTPError as e:
        return ScrapeJobURLResponse(error=f"Failed to fetch URL: {e}")

    # Parse with LLM
    llm = LLMService()
    parsed = await llm.scrape_job_from_url(html_content)

    if not parsed.get("title"):
        return ScrapeJobURLResponse(error="Could not extract job details from the page")

    # Determine source from URL
    source = JobSource.OTHER
    url_lower = data.url.lower()
    if "linkedin.com" in url_lower:
        source = JobSource.LINKEDIN
    elif "indeed.com" in url_lower:
        source = JobSource.INDEED
    elif "naukri.com" in url_lower:
        source = JobSource.NAUKRI

    # Create job listing
    job = JobListing(
        user_id=uuid.UUID(user_id),
        title=parsed.get("title", "Unknown"),
        company=parsed.get("company", "Unknown"),
        location=parsed.get("location"),
        remote_type=parsed.get("remote_type"),
        description=parsed.get("description", ""),
        requirements=parsed.get("requirements"),
        source=source,
        source_url=data.url,
        technologies=", ".join(parsed.get("skills", [])) if parsed.get("skills") else None,
        role_level=parsed.get("role_level"),
        discovered_at=datetime.now(UTC),
        is_active=True,
    )
    created_job = await job_repo.create(job)
    await db.commit()

    job_response = JobListingResponse.model_validate(created_job)

    # Optionally compute fit score
    fit_analysis = None
    if data.resume_id:
        resume_repo = ResumeRepository(db)
        resume = await resume_repo.get_by_id(uuid.UUID(data.resume_id))
        if resume:
            fit_result = await llm.compute_fit_score(
                resume_latex=resume.latex_source,
                job_description=created_job.description,
            )
            fit_analysis = JobMatchScoreResponse(
                job_id=str(created_job.id),
                match_score=fit_result.get("match_score", 0.0),
                reasoning=fit_result.get("reasoning", ""),
                matched_skills=fit_result.get("matched_skills", []),
                missing_skills=fit_result.get("missing_skills", []),
                strengths=fit_result.get("strengths", []),
                weaknesses=fit_result.get("weaknesses", []),
                recommendations=fit_result.get("recommendations", []),
            )
            # Persist score
            created_job.match_score = fit_result.get("match_score", 0.0)
            created_job.match_reasoning = fit_result.get("reasoning", "")
            await db.commit()

    return ScrapeJobURLResponse(job=job_response, fit_analysis=fit_analysis)
