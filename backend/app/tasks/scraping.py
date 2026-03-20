"""
Scraping tasks.

Celery tasks for job discovery across multiple platforms.
"""

import asyncio
import json
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
                # Deduplicate by source_url
                source_url = raw.get("url", "") or raw.get("source_url", "")
                if not source_url:
                    continue

                existing = await job_repo.get_by_source_url(source_url)
                if existing:
                    continue

                from app.models.job import JobListing, JobSource
                job = JobListing(
                    user_id=UUID(user_id),
                    title=raw.get("title", ""),
                    company=raw.get("company", ""),
                    location=raw.get("location"),
                    remote_type=raw.get("remote_type"),
                    description=raw.get("description", ""),
                    requirements=raw.get("requirements"),
                    source_url=source_url,
                    source=JobSource(raw.get("source", "other")),
                    source_job_id=raw.get("external_id") or raw.get("source_job_id"),
                    technologies=json.dumps(raw.get("skills", [])) if raw.get("skills") else None,
                    role_level=raw.get("experience_level") or raw.get("role_level"),
                    is_active=True,
                )
                session.add(job)
                saved_count += 1

            await session.commit()

            # Audit log
            await audit_repo.log_action(
                user_id=UUID(user_id),
                action="scrape_jobs",
                module="scraping",
                entity_type="job",
                details=json.dumps({
                    "keywords": keywords,
                    "location": location,
                    "sources": sources,
                    "total_found": len(raw_jobs),
                    "new_saved": saved_count,
                }),
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
            users = await user_repo.get_active_users_with_preferences()

            triggered = 0
            for user in users:
                # Read preferences from user model fields
                keywords = []
                if user.job_search_keywords:
                    keywords = [k.strip() for k in user.job_search_keywords.split(",") if k.strip()]
                if not keywords:
                    continue

                location = user.preferred_location

                scrape_jobs.delay(
                    user_id=str(user.id),
                    keywords=keywords,
                    location=location,
                )
                triggered += 1

            return {"users_triggered": triggered}

    return _run_async(_periodic())
