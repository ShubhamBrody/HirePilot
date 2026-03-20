"""
Job Application Agent

Automates job application submission using Selenium + LLM.
Navigates portal, fills forms, uploads resume, clicks submit.
"""

from __future__ import annotations

import uuid

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.core.logging import get_logger

logger = get_logger(__name__)


class ApplicationAgent(BaseAgent):
    name = "application"
    description = "Auto-apply to jobs using browser automation (Selenium + LLM)"
    max_runs_per_hour = 5
    max_runs_per_day = 20

    async def execute(self, context: AgentContext) -> AgentResult:
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.models.application import Application, ApplicationMethod, ApplicationStatus
        from app.repositories.application_repo import ApplicationRepository
        from app.repositories.job_repo import JobRepository
        from app.repositories.resume_repo import ResumeRepository
        from app.repositories.user_repo import UserRepository
        from app.services.selenium_bot import SeleniumApplicationBot

        db: AsyncSession = context.db_session
        job_id = context.params.get("job_id")
        resume_version_id = context.params.get("resume_version_id")
        application_id = context.params.get("application_id")

        if not job_id:
            return AgentResult(success=False, errors=["job_id is required"])

        user_repo = UserRepository(db)
        job_repo = JobRepository(db)
        resume_repo = ResumeRepository(db)
        app_repo = ApplicationRepository(db)

        user = await user_repo.get_by_id(uuid.UUID(context.user_id))
        job = await job_repo.get_by_id(uuid.UUID(job_id))
        if not user or not job:
            return AgentResult(success=False, errors=["User or job not found"])

        resume = None
        if resume_version_id:
            resume = await resume_repo.get_by_id(uuid.UUID(resume_version_id))

        # Get or create application record
        application = None
        if application_id:
            application = await app_repo.get_by_id(uuid.UUID(application_id))

        if not application:
            exists = await app_repo.application_exists(user.id, job.id)
            if exists:
                return AgentResult(success=False, errors=["Already applied to this job"])
            application = Application(
                id=uuid.uuid4(),
                user_id=user.id,
                job_listing_id=job.id,
                resume_version_id=uuid.UUID(resume_version_id) if resume_version_id else None,
                company=job.company,
                role=job.title,
                status=ApplicationStatus.APPLYING,
                method=ApplicationMethod.AUTOMATED,
            )
            await app_repo.create(application)
            await db.commit()

        # Build user profile for form filling
        profile = {
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone or "",
            "location": user.location or "",
            "linkedin_url": user.linkedin_url or "",
            "github_url": user.github_url or "",
            "skills": user.skills or "",
            "headline": user.headline or "",
        }

        bot = SeleniumApplicationBot()
        result = await bot.apply_to_job(
            job_url=job.source_url,
            resume_path=resume.pdf_s3_key if resume else None,
            user_profile=profile,
        )

        if result.get("status") == "success":
            application.status = ApplicationStatus.APPLIED
            data = {"application_id": str(application.id), "log": result.get("action_log", [])}
        else:
            application.status = ApplicationStatus.DRAFT
            application.automation_error = result.get("error", "Unknown error")
            data = {"application_id": str(application.id), "error": result.get("error")}

        await db.commit()

        return AgentResult(
            success=result.get("status") == "success",
            data=data,
            errors=[result.get("error")] if result.get("error") else [],
            items_processed=1,
        )
