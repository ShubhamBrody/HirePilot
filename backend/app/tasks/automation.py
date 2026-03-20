"""
Automation tasks.

Celery tasks for job application automation using Selenium + LLM.
"""

import asyncio
import json
import tempfile
from datetime import datetime, timedelta, UTC
from typing import Any
from uuid import UUID

from app.tasks import celery_app
from app.core.database import async_session_factory
from app.core.logging import get_logger
from app.services.selenium_bot import SeleniumApplicationBot
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
    application_id_or_job_id: str,
    extra_data: dict | str | None = None,
    cover_letter: str | None = None,
) -> dict[str, Any]:
    """
    Automatically apply to a job using Selenium + LLM browser automation.

    Supports two call styles:
    - Wizard flow: auto_apply_job(user_id, application_id, {})
    - Legacy flow: auto_apply_job(user_id, job_listing_id, resume_version_id, cover_letter)

    Steps:
      1. Load user credentials, job listing, and resume
      2. Compile resume to PDF (or download from S3)
      3. Launch SeleniumApplicationBot
      4. Apply and record result
    """
    logger.info(
        "Starting auto-apply (Selenium)",
        user_id=user_id,
        id=application_id_or_job_id,
    )

    async def _apply():
        async with async_session_factory() as session:
            user_repo = UserRepository(session)
            job_repo = JobRepository(session)
            resume_repo = ResumeRepository(session)
            app_repo = ApplicationRepository(session)
            audit_repo = AuditLogRepository(session)

            user = await user_repo.get_by_id(UUID(user_id))
            if not user:
                return {"error": "User not found", "success": False}

            # Determine if we were given an application_id (wizard) or a job_listing_id (legacy)
            application = await app_repo.get_by_id(UUID(application_id_or_job_id))
            if application:
                # Wizard flow — application already created with linked resume
                job = await job_repo.get_by_id(application.job_listing_id)
                resume = await resume_repo.get_by_id(application.resume_version_id)
            else:
                # Legacy flow — application_id_or_job_id is the job_listing_id
                job = await job_repo.get_by_id(UUID(application_id_or_job_id))
                resume_version_id = extra_data if isinstance(extra_data, str) else None
                resume = await resume_repo.get_by_id(UUID(resume_version_id)) if resume_version_id else None
                if not resume:
                    resume = await resume_repo.get_master_resume(UUID(user_id))
                application = None

            if not job:
                return {"error": "Job listing not found", "success": False}
            if not resume:
                return {"error": "No resume found", "success": False}

            # Create application record if not from wizard
            from app.models.application import Application, ApplicationStatus, ApplicationMethod
            if not application:
                already_applied = await app_repo.application_exists(
                    user_id=UUID(user_id),
                    job_listing_id=job.id,
                )
                if already_applied:
                    return {"error": "Already applied to this job", "success": False}

                application = Application(
                    user_id=UUID(user_id),
                    job_listing_id=job.id,
                    resume_version_id=resume.id,
                    company=job.company,
                    role=job.title,
                    job_description_snapshot=job.description[:2000] if job.description else None,
                    status=ApplicationStatus.APPLYING,
                    method=ApplicationMethod.AUTOMATED,
                    cover_letter=cover_letter,
                )
                session.add(application)
                await session.flush()
            else:
                application.status = ApplicationStatus.APPLYING
                session.add(application)
                await session.flush()

            # Prepare resume PDF path
            # First try to compile from LaTeX if available
            resume_pdf_path = None
            if resume.latex_source:
                try:
                    from app.services.latex_compiler import LatexCompilerService
                    compiler = LatexCompilerService()
                    pdf_bytes = await compiler.compile_latex(resume.latex_source)
                    if pdf_bytes:
                        import os
                        tmp = tempfile.NamedTemporaryFile(
                            suffix=".pdf", prefix="resume_", delete=False
                        )
                        tmp.write(pdf_bytes)
                        tmp.close()
                        resume_pdf_path = tmp.name
                except Exception as e:
                    logger.warning("PDF compilation failed, attempting S3 download", error=str(e))

            # If compilation failed, try downloading from S3
            if not resume_pdf_path and resume.pdf_s3_key:
                try:
                    from app.services.storage import StorageService
                    storage = StorageService()
                    pdf_data = await storage.download(resume.pdf_s3_key)
                    if pdf_data:
                        tmp = tempfile.NamedTemporaryFile(
                            suffix=".pdf", prefix="resume_", delete=False
                        )
                        tmp.write(pdf_data)
                        tmp.close()
                        resume_pdf_path = tmp.name
                except Exception as e:
                    logger.warning("S3 download failed", error=str(e))

            if not resume_pdf_path:
                application.status = ApplicationStatus.DRAFT
                application.automation_error = "Could not generate resume PDF"
                session.add(application)
                await session.commit()
                return {"error": "Could not generate resume PDF", "success": False}

            # Build user profile for form filling
            user_profile = {
                "full_name": user.full_name or "",
                "first_name": (user.full_name or "").split()[0] if user.full_name else "",
                "last_name": " ".join((user.full_name or "").split()[1:]) if user.full_name else "",
                "email": user.email or "",
                "phone": getattr(user, "phone", "") or "",
                "linkedin_url": getattr(user, "linkedin_url", "") or "",
                "linkedin": getattr(user, "linkedin_url", "") or "",
                "github_url": getattr(user, "github_url", "") or "",
                "portfolio_url": getattr(user, "portfolio_url", "") or "",
                "location": getattr(user, "preferred_location", "") or getattr(user, "location", "") or "",
                "current_company": getattr(user, "current_company", "") or "",
                "current_title": getattr(user, "current_title", "") or "",
                "years_experience": str(getattr(user, "years_of_experience", "") or ""),
                "work_authorization": getattr(user, "work_authorization", "") or "",
                "notice_period": str(getattr(user, "notice_period_days", "") or ""),
                "expected_salary": str(getattr(user, "expected_salary_min", "") or ""),
                "current_salary": str(getattr(user, "current_salary_ctc", "") or ""),
                "gender": getattr(user, "gender", "") or "",
                "nationality": getattr(user, "nationality", "") or "",
                "disability_status": getattr(user, "disability_status", "") or "",
                "veteran_status": getattr(user, "veteran_status", "") or "",
                "headline": getattr(user, "headline", "") or "",
                "cover_letter": getattr(user, "cover_letter_default", "") or "",
            }

            # Run Selenium bot
            bot = SeleniumApplicationBot()
            result = bot.apply_to_job(
                job_url=job.source_url,
                resume_pdf_path=resume_pdf_path,
                user_profile=user_profile,
                cover_letter=cover_letter,
            )

            # Clean up temp file
            try:
                import os
                os.unlink(resume_pdf_path)
            except Exception:
                pass

            # Update application based on result
            if result.get("success"):
                application.status = ApplicationStatus.APPLIED
                application.applied_date = datetime.now(UTC)
                application.notes = "Auto-applied via Selenium bot"
            else:
                application.status = ApplicationStatus.DRAFT
                application.automation_error = result.get("error", "Unknown error")
                application.notes = f"Auto-apply failed: {result.get('error', 'Unknown')}"

            application.automation_log = json.dumps(result.get("action_log", []))
            application.form_data_snapshot = json.dumps(user_profile)
            session.add(application)

            # Audit
            await audit_repo.log_action(
                user_id=UUID(user_id),
                action="auto_apply",
                module="automation",
                entity_type="application",
                entity_id=str(application.id),
                details=json.dumps({
                    "job_id": str(job.id),
                    "success": result.get("success", False),
                    "method": "selenium",
                    "status": result.get("status", "unknown"),
                }),
            )
            await session.commit()

            return {
                "application_id": str(application.id),
                "success": result.get("success", False),
                "status": result.get("status", "unknown"),
                "message": result.get("error") or "Applied successfully",
                "action_log": result.get("action_log", []),
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
    Mark applications with no status update in 30 days as WITHDRAWN.
    Runs daily via Celery Beat.
    """

    async def _cleanup():
        async with async_session_factory() as session:
            app_repo = ApplicationRepository(session)
            cutoff = datetime.now(UTC) - timedelta(days=30)
            count = await app_repo.mark_stale_as_withdrawn(cutoff)
            await session.commit()
            return {"marked_withdrawn": count}

    return _run_async(_cleanup())


@celery_app.task(name="app.tasks.automation.purge_expired_trash")
def purge_expired_trash() -> dict[str, Any]:
    """
    Permanently delete items soft-deleted more than 20 days ago.
    Runs daily via Celery Beat.
    """
    from app.repositories.recruiter_repo import RecruiterRepository

    async def _purge():
        async with async_session_factory() as session:
            totals = {}
            for name, repo_cls in [
                ("applications", ApplicationRepository),
                ("jobs", JobRepository),
                ("resumes", ResumeRepository),
                ("recruiters", RecruiterRepository),
            ]:
                repo = repo_cls(session)
                count = await repo.permanent_delete_expired(days=20)
                totals[name] = count
            await session.commit()
            logger.info("Trash purge complete", **totals)
            return totals

    return _run_async(_purge())
