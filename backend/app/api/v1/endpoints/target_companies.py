"""
Target Companies Endpoints — CRUD, URL discovery, scraping triggers.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger
from app.core.security import get_current_user_id
from app.models.target_company import TargetCompany, URLDiscoveryMethod
from app.repositories.target_company_repo import (
    ScrapingLogRepository,
    TargetCompanyRepository,
)
from app.schemas.target_company import (
    BulkCompanyCreate,
    CompanySearchSettingsUpdate,
    DiscoverURLResponse,
    ScrapeCompanyResponse,
    ScrapingLogListResponse,
    ScrapingLogResponse,
    TargetCompanyCreate,
    TargetCompanyListResponse,
    TargetCompanyResponse,
    TargetCompanyUpdate,
)

logger = get_logger(__name__)
router = APIRouter()


# ── Helpers ──────────────────────────────────────────────────


async def _get_plan_limits(db: AsyncSession, user_id: str) -> dict:
    """Get the user's subscription plan limits for company search."""
    from app.models.subscription import PLAN_CONFIGS, Subscription
    from sqlalchemy import select

    stmt = select(Subscription).where(
        Subscription.user_id == uuid.UUID(user_id),
        Subscription.status == "active",
    )
    result = await db.execute(stmt)
    sub = result.scalar_one_or_none()
    plan = sub.plan if sub else "free"
    return PLAN_CONFIGS.get(plan, PLAN_CONFIGS["free"])


# ── CRUD Endpoints ───────────────────────────────────────────


@router.get("", response_model=TargetCompanyListResponse)
async def list_target_companies(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    enabled_only: bool = Query(False),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List all target companies for the current user."""
    repo = TargetCompanyRepository(db)
    companies = await repo.get_user_companies(
        uuid.UUID(user_id), skip=skip, limit=limit, enabled_only=enabled_only
    )
    total = await repo.count_user_companies(uuid.UUID(user_id))
    return TargetCompanyListResponse(
        companies=[TargetCompanyResponse.model_validate(c) for c in companies],
        total=total,
    )


@router.post("", response_model=TargetCompanyResponse, status_code=status.HTTP_201_CREATED)
async def add_target_company(
    data: TargetCompanyCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Add a company to track for career page job scraping."""
    repo = TargetCompanyRepository(db)

    # Check plan limits
    limits = await _get_plan_limits(db, user_id)
    current_count = await repo.count_user_companies(uuid.UUID(user_id))
    max_companies = limits.get("max_target_companies", 3)
    if current_count >= max_companies:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Plan limit reached: maximum {max_companies} target companies allowed. Upgrade to add more.",
        )

    # Check frequency limit
    min_freq = limits.get("min_scrape_frequency_hours", 24)
    if data.scrape_frequency_hours < min_freq:
        data.scrape_frequency_hours = min_freq

    # Check duplicate
    existing = await repo.get_by_name(uuid.UUID(user_id), data.company_name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Company '{data.company_name}' is already in your target list.",
        )

    company = TargetCompany(
        user_id=uuid.UUID(user_id),
        company_name=data.company_name.strip(),
        career_page_url=data.career_page_url,
        url_discovery_method=URLDiscoveryMethod.USER_PROVIDED if data.career_page_url else None,
        url_verified=bool(data.career_page_url),
        scrape_frequency_hours=data.scrape_frequency_hours,
    )
    company = await repo.create(company)
    await db.commit()
    return TargetCompanyResponse.model_validate(company)


@router.put("/{company_id}", response_model=TargetCompanyResponse)
async def update_target_company(
    company_id: str,
    data: TargetCompanyUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Update a target company's settings."""
    repo = TargetCompanyRepository(db)
    company = await repo.get_by_id(uuid.UUID(company_id))
    if not company or str(company.user_id) != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    update_data = data.model_dump(exclude_unset=True)

    # Enforce frequency limits
    if "scrape_frequency_hours" in update_data:
        limits = await _get_plan_limits(db, user_id)
        min_freq = limits.get("min_scrape_frequency_hours", 24)
        if update_data["scrape_frequency_hours"] < min_freq:
            update_data["scrape_frequency_hours"] = min_freq

    if "career_page_url" in update_data and update_data["career_page_url"]:
        update_data["url_discovery_method"] = URLDiscoveryMethod.USER_PROVIDED
        update_data["url_verified"] = True

    company = await repo.update(company, update_data)
    await db.commit()
    return TargetCompanyResponse.model_validate(company)


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_target_company(
    company_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Remove a company from the target list."""
    repo = TargetCompanyRepository(db)
    company = await repo.get_by_id(uuid.UUID(company_id))
    if not company or str(company.user_id) != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    await repo.delete(company)
    await db.commit()


@router.post("/bulk", response_model=TargetCompanyListResponse, status_code=status.HTTP_201_CREATED)
async def bulk_add_companies(
    data: BulkCompanyCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Add multiple companies at once."""
    repo = TargetCompanyRepository(db)

    # Check plan limits
    limits = await _get_plan_limits(db, user_id)
    current_count = await repo.count_user_companies(uuid.UUID(user_id))
    max_companies = limits.get("max_target_companies", 3)
    available_slots = max_companies - current_count

    if available_slots <= 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Plan limit reached: maximum {max_companies} target companies allowed.",
        )

    min_freq = limits.get("min_scrape_frequency_hours", 24)
    freq = max(data.scrape_frequency_hours, min_freq)

    created = []
    for name in data.company_names[:available_slots]:
        name = name.strip()
        if not name:
            continue
        existing = await repo.get_by_name(uuid.UUID(user_id), name)
        if existing:
            continue
        company = TargetCompany(
            user_id=uuid.UUID(user_id),
            company_name=name,
            scrape_frequency_hours=freq,
        )
        company = await repo.create(company)
        created.append(company)

    await db.commit()
    return TargetCompanyListResponse(
        companies=[TargetCompanyResponse.model_validate(c) for c in created],
        total=len(created),
    )


# ── Discovery & Scraping ────────────────────────────────────


@router.post("/{company_id}/discover-url", response_model=DiscoverURLResponse)
async def discover_career_url(
    company_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Use AI to discover the company's career page URL."""
    repo = TargetCompanyRepository(db)
    company = await repo.get_by_id(uuid.UUID(company_id))
    if not company or str(company.user_id) != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    from app.services.career_discovery import CareerPageDiscoveryService
    from app.services.llm_service import LLMService

    discovery = CareerPageDiscoveryService(LLMService())
    result = await discovery.discover_career_url(company.company_name)

    # Update the company if a URL was found
    if result.get("career_url"):
        company.career_page_url = result["career_url"]
        company.url_discovery_method = URLDiscoveryMethod.AI_DISCOVERED
        company.url_verified = False
        await db.commit()

    return DiscoverURLResponse(**result)


@router.post("/{company_id}/scrape", response_model=ScrapeCompanyResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_scrape(
    company_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger a scrape for a specific company."""
    repo = TargetCompanyRepository(db)
    company = await repo.get_by_id(uuid.UUID(company_id))
    if not company or str(company.user_id) != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    if not company.career_page_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No career page URL set. Use 'Discover URL' first.",
        )

    from app.tasks.agent_tasks import run_agent

    task = run_agent.delay("company_search", user_id, {"target_company_id": company_id})

    return ScrapeCompanyResponse(
        message=f"Scrape started for {company.company_name}",
        task_id=task.id,
    )


@router.get("/{company_id}/scraping-logs", response_model=ScrapingLogListResponse)
async def get_scraping_logs(
    company_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get scraping history for a specific company."""
    tc_repo = TargetCompanyRepository(db)
    company = await tc_repo.get_by_id(uuid.UUID(company_id))
    if not company or str(company.user_id) != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    log_repo = ScrapingLogRepository(db)
    logs = await log_repo.get_company_logs(uuid.UUID(company_id), skip=skip, limit=limit)
    total = await log_repo.count_company_logs(uuid.UUID(company_id))
    return ScrapingLogListResponse(
        logs=[ScrapingLogResponse.model_validate(log) for log in logs],
        total=total,
    )


# ── User Search Settings ────────────────────────────────────


@router.patch("/settings", response_model=dict)
async def update_search_settings(
    data: CompanySearchSettingsUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Update the user's company search settings (toggle, threshold)."""
    from app.repositories.user_repo import UserRepository

    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(uuid.UUID(user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if hasattr(user, key):
            setattr(user, key, value)

    await db.commit()
    return {
        "company_search_enabled": user.company_search_enabled,
        "linkedin_search_enabled": user.linkedin_search_enabled,
        "auto_apply_threshold": user.auto_apply_threshold,
    }


# ── Progress / Activity Feed ────────────────────────────────


@router.get("/activity", response_model=dict)
async def get_activity_feed(
    limit: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get a combined activity feed: recent scraping logs + summary stats."""
    from sqlalchemy import desc, func, select

    from app.models.scraping_log import CompanyScrapingLog
    from app.models.target_company import TargetCompany

    uid = uuid.UUID(user_id)

    # Summary stats
    stats_q = (
        select(
            func.count().label("total_companies"),
            func.sum(TargetCompany.jobs_found_total).label("total_jobs_found"),
        )
        .where(TargetCompany.user_id == uid)
    )
    stats_result = await db.execute(stats_q)
    stats_row = stats_result.one()

    active_q = (
        select(func.count())
        .select_from(TargetCompany)
        .where(TargetCompany.user_id == uid, TargetCompany.is_enabled.is_(True))
    )
    active_result = await db.execute(active_q)
    active_count = active_result.scalar_one()

    # Recent scraping logs
    logs_q = (
        select(CompanyScrapingLog)
        .join(TargetCompany, CompanyScrapingLog.target_company_id == TargetCompany.id)
        .where(TargetCompany.user_id == uid)
        .order_by(desc(CompanyScrapingLog.started_at))
        .limit(limit)
    )
    logs_result = await db.execute(logs_q)
    logs = logs_result.scalars().all()

    return {
        "summary": {
            "total_companies": stats_row.total_companies or 0,
            "active_companies": active_count,
            "total_jobs_found": stats_row.total_jobs_found or 0,
        },
        "recent_activity": [
            {
                "id": str(log.id),
                "target_company_id": str(log.target_company_id),
                "started_at": log.started_at.isoformat() if log.started_at else None,
                "completed_at": log.completed_at.isoformat() if log.completed_at else None,
                "status": log.status.value if log.status else None,
                "jobs_found": log.jobs_found,
                "new_jobs_saved": log.new_jobs_saved,
                "error_message": log.error_message,
                "duration_seconds": log.duration_seconds,
            }
            for log in logs
        ],
    }
