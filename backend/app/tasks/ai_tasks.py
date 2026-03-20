"""
AI tasks.

Celery tasks for AI-powered operations: resume tailoring, match scoring, compilation.
Uses Ollama LLM via LLMService instead of OpenAI.
"""

import asyncio
import json
from typing import Any
from uuid import UUID

from app.tasks import celery_app
from app.core.database import async_session_factory
from app.core.logging import get_logger
from app.services.llm_service import LLMService
from app.services.latex_compiler import LatexCompilerService
from app.services.storage import StorageService
from app.repositories.resume_repo import ResumeRepository
from app.repositories.job_repo import JobRepository
from app.repositories.audit_repo import AuditLogRepository

logger = get_logger(__name__)


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    name="app.tasks.ai.tailor_resume",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def tailor_resume(
    self,
    user_id: str,
    resume_version_id: str,
    job_listing_id: str,
) -> dict[str, Any]:
    """
    Tailor a resume for a specific job listing using Ollama AI.

    Pipeline:
      1. Load source resume LaTeX + job description
      2. AI tailors resume for the JD
      3. Compile tailored LaTeX to PDF
      4. Store PDF in S3
      5. Save new ResumeVersion
    """
    logger.info(
        "Starting resume tailoring",
        user_id=user_id,
        resume_id=resume_version_id,
        job_id=job_listing_id,
    )

    async def _tailor():
        async with async_session_factory() as session:
            resume_repo = ResumeRepository(session)
            job_repo = JobRepository(session)
            audit_repo = AuditLogRepository(session)

            llm = LLMService()
            compiler = LatexCompilerService()
            storage = StorageService()

            # 1. Load source resume and job
            source_resume = await resume_repo.get_by_id(UUID(resume_version_id))
            if not source_resume:
                return {"error": "Resume version not found"}

            job = await job_repo.get_by_id(UUID(job_listing_id))
            if not job:
                return {"error": "Job listing not found"}

            # 2. AI tailoring via Ollama
            tailored_result = await llm.tailor_resume(
                master_latex=source_resume.latex_source,
                job_description=job.description,
                company=job.company,
                role=job.title,
            )
            tailored_latex = tailored_result.get("tailored_latex", "")

            # Generate changes summary
            changes_result = await llm.generate_changes_summary(
                source_resume.latex_source, tailored_latex
            )
            changes = changes_result.get("changes_summary", "")

            # 3. Compile to PDF
            compile_result = await compiler.compile(tailored_latex)

            # 4. Store PDF if compilation succeeded
            pdf_s3_key = None
            if compile_result["success"] and compile_result["pdf_data"]:
                pdf_s3_key = await storage.upload_resume_pdf(
                    user_id=user_id,
                    filename=f"tailored_{job.company}_{job.title}.pdf".replace(" ", "_"),
                    pdf_data=compile_result["pdf_data"],
                )

            # 5. Create new resume version
            from app.models.resume import ResumeVersion
            new_version = ResumeVersion(
                user_id=UUID(user_id),
                name=f"Tailored for {job.title} @ {job.company}",
                latex_source=tailored_latex,
                is_master=False,
                version_number=await resume_repo.get_next_version_number(UUID(user_id)),
                pdf_s3_key=pdf_s3_key,
                compilation_status="success" if compile_result["success"] else "failed",
                compilation_errors=json.dumps(compile_result.get("errors", [])),
                tailored_for_job_id=job.id,
                ai_tailored=True,
                ai_changes_summary=changes,
                target_company=job.company,
                target_role=job.title,
            )
            session.add(new_version)

            # 6. Compute and update match score
            score_result = await llm.compute_fit_score(
                tailored_latex, job.description
            )
            match_score = score_result.get("match_score", 0.0)
            job.match_score = match_score
            job.match_reasoning = score_result.get("reasoning", "")
            session.add(job)

            await session.commit()

            # Audit
            await audit_repo.log_action(
                user_id=UUID(user_id),
                action="tailor_resume",
                module="ai",
                entity_type="resume",
                entity_id=str(new_version.id),
                details=json.dumps({
                    "source_resume_id": resume_version_id,
                    "job_id": job_listing_id,
                    "match_score": match_score,
                    "compiled": compile_result["success"],
                }),
            )
            await session.commit()

            return {
                "new_version_id": str(new_version.id),
                "pdf_s3_key": pdf_s3_key,
                "match_score": match_score,
                "changes_summary": changes,
                "compiled": compile_result["success"],
                "compilation_errors": compile_result.get("errors", []),
            }

    try:
        return _run_async(_tailor())
    except Exception as exc:
        logger.error("Resume tailoring failed", error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.ai.batch_match_score",
    bind=True,
    max_retries=2,
)
def batch_match_score(self, user_id: str) -> dict[str, Any]:
    """
    Compute match scores for all unscored jobs against the user's master resume.
    """
    logger.info("Starting batch match scoring", user_id=user_id)

    async def _batch():
        async with async_session_factory() as session:
            resume_repo = ResumeRepository(session)
            job_repo = JobRepository(session)
            llm = LLMService()

            master = await resume_repo.get_master_resume(UUID(user_id))
            if not master:
                return {"error": "No master resume found"}

            unscored = await job_repo.get_unscored_jobs(UUID(user_id))
            scored = 0

            for job in unscored:
                try:
                    result = await llm.compute_fit_score(
                        master.latex_source, job.description
                    )
                    job.match_score = result.get("match_score", 0.0)
                    job.match_reasoning = result.get("reasoning", "")
                    session.add(job)
                    scored += 1
                except Exception as e:
                    logger.warning("Match score failed for job", job_id=str(job.id), error=str(e))

            await session.commit()
            return {"scored": scored, "total_unscored": len(unscored)}

    try:
        return _run_async(_batch())
    except Exception as exc:
        logger.error("Batch matching failed", error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(name="app.tasks.ai.compile_resume")
def compile_resume(user_id: str, resume_version_id: str) -> dict[str, Any]:
    """
    Compile a resume version's LaTeX to PDF and store the result.
    """

    async def _compile():
        async with async_session_factory() as session:
            resume_repo = ResumeRepository(session)
            compiler = LatexCompilerService()
            storage = StorageService()

            resume = await resume_repo.get_by_id(UUID(resume_version_id))
            if not resume:
                return {"error": "Resume not found"}

            result = await compiler.compile(resume.latex_source)

            pdf_s3_key = None
            if result["success"] and result["pdf_data"]:
                pdf_s3_key = await storage.upload_resume_pdf(
                    user_id=user_id,
                    filename=f"{resume.name}.pdf".replace(" ", "_"),
                    pdf_data=result["pdf_data"],
                )

            resume.compilation_status = "success" if result["success"] else "failed"
            resume.compilation_errors = json.dumps(result.get("errors", []))
            resume.pdf_s3_key = pdf_s3_key
            session.add(resume)
            await session.commit()

            return {
                "compiled": result["success"],
                "pdf_s3_key": pdf_s3_key,
                "errors": result.get("errors", []),
                "warnings": result.get("warnings", []),
            }

    return _run_async(_compile())
