"""
Scraping tasks.

Celery tasks for job discovery across multiple platforms.
"""

import asyncio
from typing import Any
from uuid import UUID

from app.tasks import celery_app
from app.core.database import async_session_factory
from app.core.logging import get_logger
from app.services.job_scraper import JobScraperOrchestrator
from app.repositories.job_repo import JobRepository
from app.repositories.user_repo import UserRepository
from app.repositories.audit_repo import AuditLogRepository

logger = get_logger(__name__)


def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    name="app.tasks.scraping.scrape_jobs",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def scrape_jobs(
    self,
    user_id: str,
    keywords: list[str],
    location: str | None = None,
    sources: list[str] | None = None,
) -> dict[str, Any]:
    """
    Scrape jobs from configured sources for a user.

    Args:
        user_id: UUID of the requesting user.
        keywords: Job title / skill keywords.
        location: Optional location filter.
        sources: Optional list of sources to scrape ["linkedin", "indeed", "naukri"].
    """
    logger.info(
        "Starting job scrape task",
        user_id=user_id,
        keywords=keywords,
        location=location,
    )

    async def _scrape():
        async with async_session_factory() as session:
            job_repo = JobRepository(session)
            audit_repo = AuditLogRepository(session)
            orchestrator = JobScraperOrchestrator()

            raw_jobs = await orchestrator.scrape_all(
                keywords=keywords,
                location=location,
                sources=sources,
            )

            saved_count = 0
            for raw in raw_jobs:
                # Deduplicate by external_id + source
                existing = await job_repo.find_by_external_id(
                    raw.get("external_id", ""),
                    raw.get("source", ""),
                )
                if existing:
                    continue

                from app.models.job import JobListing, JobSource
                job = JobListing(
                    user_id=UUID(user_id),
                    title=raw.get("title", ""),
                    company=raw.get("company", ""),
                    location=raw.get("location"),
                    description=raw.get("description", ""),
                    url=raw.get("url", ""),
                    source=JobSource(raw.get("source", "other")),
                    external_id=raw.get("external_id"),
                    salary_range=raw.get("salary_range"),
                    job_type=raw.get("job_type"),
                    experience_level=raw.get("experience_level"),
                    skills=raw.get("skills", []),
                )
                session.add(job)
                saved_count += 1

            await session.commit()

            # Audit log
            audit = await audit_repo.log_action(
                user_id=UUID(user_id),
                action="scrape_jobs",
                resource_type="job",
                details={
                    "keywords": keywords,
                    "location": location,
                    "sources": sources,
                    "total_found": len(raw_jobs),
                    "new_saved": saved_count,
                },
            )
            await session.commit()

            return {
                "total_found": len(raw_jobs),
                "new_saved": saved_count,
            }

    try:
        return _run_async(_scrape())
    except Exception as exc:
        logger.error("Job scrape failed", error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.scraping.scrape_jobs_periodic",
)
def scrape_jobs_periodic() -> dict[str, Any]:
    """
    Periodic task: scrape jobs for all active users based on their saved preferences.
    Triggered by Celery Beat every 6 hours.
    """
    logger.info("Starting periodic job scrape")

    async def _periodic():
        async with async_session_factory() as session:
            user_repo = UserRepository(session)
            # Fetch users with saved job preferences
            users = await user_repo.get_active_users_with_preferences()

            triggered = 0
            for user in users:
                prefs = user.job_preferences or {}
                keywords = prefs.get("keywords", [])
                if not keywords:
                    continue

                # Dispatch individual scrape task per user
                scrape_jobs.delay(
                    user_id=str(user.id),
                    keywords=keywords,
                    location=prefs.get("location"),
                    sources=prefs.get("sources"),
                )
                triggered += 1

            return {"users_triggered": triggered}

    return _run_async(_periodic())
