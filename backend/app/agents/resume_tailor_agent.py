"""
Resume Tailor Agent

Takes a job description + master resume, creates a tailored version,
and stores it linked to the job for the approval flow.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.core.logging import get_logger

logger = get_logger(__name__)


class ResumeTailorAgent(BaseAgent):
    name = "resume_tailor"
    description = "AI-tailor your resume for a specific job description"
    max_runs_per_hour = 10
    max_runs_per_day = 50

    async def execute(self, context: AgentContext) -> AgentResult:
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.models.resume import ResumeVersion
        from app.repositories.job_repo import JobRepository
        from app.repositories.resume_repo import ResumeRepository
        from app.repositories.user_repo import UserRepository
        from app.services.llm_service import LLMService

        db: AsyncSession = context.db_session
        llm = context.llm_service or LLMService()
        job_id = context.params.get("job_id")
        user_message = context.params.get("user_message")
        existing_latex = context.params.get("current_latex")

        if not job_id:
            return AgentResult(success=False, errors=["job_id is required"])

        user_repo = UserRepository(db)
        job_repo = JobRepository(db)
        resume_repo = ResumeRepository(db)

        user = await user_repo.get_by_id(uuid.UUID(context.user_id))
        job = await job_repo.get_by_id(uuid.UUID(job_id))
        if not user or not job:
            return AgentResult(success=False, errors=["User or job not found"])

        base_latex = existing_latex or user.master_resume_latex
        if not base_latex:
            return AgentResult(success=False, errors=["No master resume found. Upload a resume first."])

        # If user_message is provided, use chat-style modification
        if user_message and existing_latex:
            tailored = await llm.chat_resume(existing_latex, user_message)
        else:
            result = await llm.tailor_resume(base_latex, job.description, job.company, job.title)
            tailored = result.get("tailored_latex", "")

        if not tailored:
            return AgentResult(success=False, errors=["LLM returned empty result"])

        changes = await llm.generate_changes_summary(base_latex, str(tailored))
        score = await llm.compute_fit_score(str(tailored), job.description)

        next_version = await resume_repo.get_next_version_number(user.id)
        version = ResumeVersion(
            id=uuid.uuid4(),
            user_id=user.id,
            name=f"Tailored for {job.company} - {job.title}",
            version_number=next_version,
            latex_source=tailored,
            target_company=job.company,
            target_role=job.title,
            tailored_for_job_id=job.id,
            ai_tailored=True,
            ai_changes_summary=changes,
            is_master=False,
            created_at=datetime.now(UTC),
        )
        await resume_repo.create(version)
        await db.commit()

        return AgentResult(
            success=True,
            data={
                "resume_version_id": str(version.id),
                "tailored_latex": tailored,
                "changes_summary": changes,
                "match_score": score,
                "job_id": job_id,
            },
            items_processed=1,
        )
