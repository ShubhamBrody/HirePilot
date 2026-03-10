"""
Automation tasks.

Celery tasks for job application automation.
"""

import asyncio
from datetime import datetime, timedelta, UTC
from typing import Any
from uuid import UUID

from app.tasks import celery_app
from app.core.database import async_session_factory
from app.core.logging import get_logger
from app.services.application_bot import ApplicationBot
from app.repositories.application_repo import ApplicationRepository
from app.repositories.job_repo import JobRepository
from app.repositories.resume_repo import ResumeRepository
from app.repositories.user_repo import UserRepository
from app.repositories.audit_repo import AuditLogRepository

logger = get_logger(__name__)


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    name="app.tasks.automation.auto_apply_job",
    bind=True,
    max_retries=1,
    default_retry_delay=600,
)
def auto_apply_job(
    self,
    user_id: str,
    job_listing_id: str,
    resume_version_id: str,
    cover_letter: str | None = None,
) -> dict[str, Any]:
    """
    Automatically apply to a job using Playwright browser automation.

    Steps:
      1. Load user credentials, job listing, and resume
      2. Launch ApplicationBot
      3. Apply and record result
    """
    logger.info(
        "Starting auto-apply",
        user_id=user_id,
        job_id=job_listing_id,
    )

    async def _apply():
        async with async_session_factory() as session:
            user_repo = UserRepository(session)
            job_repo = JobRepository(session)
            resume_repo = ResumeRepository(session)
            app_repo = ApplicationRepository(session)
            audit_repo = AuditLogRepository(session)

            user = await user_repo.get(UUID(user_id))
            job = await job_repo.get(UUID(job_listing_id))
            resume = await resume_repo.get(UUID(resume_version_id))

            if not user or not job or not resume:
                return {"error": "User, job, or resume not found"}

            # Check if already applied
            existing = await app_repo.find_existing(
                user_id=UUID(user_id),
                job_listing_id=UUID(job_listing_id),
            )
            if existing:
                return {"error": "Already applied to this job", "application_id": str(existing.id)}

            # Decrypt platform credentials
            from app.core.security import decrypt_credential
            platform_creds = {}
            if user.encrypted_platform_credentials:
                import json
                platform_creds = json.loads(
                    decrypt_credential(user.encrypted_platform_credentials)
                )

            # Create application record (pending)
            from app.models.application import Application, ApplicationStatus, ApplicationMethod
            application = Application(
                user_id=UUID(user_id),
                job_listing_id=UUID(job_listing_id),
                resume_version_id=UUID(resume_version_id),
                status=ApplicationStatus.APPLIED,
                method=ApplicationMethod.AUTO_BOT,
                cover_letter=cover_letter,
                applied_date=datetime.now(UTC),
            )
            session.add(application)
            await session.flush()

            # Run the bot
            bot = ApplicationBot()
            result = await bot.apply(
                job_url=job.url,
                platform_credentials=platform_creds,
                resume_pdf_url=resume.pdf_url,
                cover_letter=cover_letter,
                user_info={
                    "full_name": user.full_name,
                    "email": user.email,
                    "phone": getattr(user, "phone", None),
                },
            )

            # Update application based on result
            if result.get("success"):
                application.status = ApplicationStatus.APPLIED
                application.notes = f"Auto-applied successfully. Confirmation: {result.get('confirmation', 'N/A')}"
            else:
                application.status = ApplicationStatus.SAVED
                application.notes = f"Auto-apply failed: {result.get('error', 'Unknown error')}"

            session.add(application)

            # Audit
            await audit_repo.log_action(
                user_id=UUID(user_id),
                action="auto_apply",
                resource_type="application",
                resource_id=application.id,
                details={
                    "job_id": job_listing_id,
                    "success": result.get("success", False),
                    "method": "auto_bot",
                },
            )
            await session.commit()

            return {
                "application_id": str(application.id),
                "success": result.get("success", False),
                "message": result.get("error") or "Applied successfully",
            }

    try:
        return _run_async(_apply())
    except Exception as exc:
        logger.error("Auto-apply failed", error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.automation.bulk_auto_apply",
)
def bulk_auto_apply(
    user_id: str,
    job_ids: list[str],
    resume_version_id: str,
) -> dict[str, Any]:
    """
    Queue auto-apply tasks for multiple jobs.
    """
    results = []
    for job_id in job_ids:
        task = auto_apply_job.delay(
            user_id=user_id,
            job_listing_id=job_id,
            resume_version_id=resume_version_id,
        )
        results.append({"job_id": job_id, "task_id": str(task.id)})

    return {"queued": len(results), "tasks": results}


@celery_app.task(name="app.tasks.automation.cleanup_stale_applications")
def cleanup_stale_applications() -> dict[str, Any]:
    """
    Mark applications with no status update in 30 days as NO_RESPONSE.
    Runs daily via Celery Beat.
    """

    async def _cleanup():
        async with async_session_factory() as session:
            app_repo = ApplicationRepository(session)
            cutoff = datetime.now(UTC) - timedelta(days=30)
            count = await app_repo.mark_stale_as_no_response(cutoff)
            await session.commit()
            return {"marked_no_response": count}

    return _run_async(_cleanup())
