"""
ATS Scoring Agent

Evaluates how well a tailored resume matches a job description
from an ATS (Applicant Tracking System) perspective.

Provides:
  - Overall ATS compatibility score (0–100)
  - Section-by-section breakdown
  - Keyword match analysis
  - Actionable improvement suggestions
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.core.logging import get_logger

logger = get_logger(__name__)

ATS_SCORING_SYSTEM_PROMPT = """\
You are an expert ATS (Applicant Tracking System) analyzer. Your job is to
score a resume against a job description exactly the way a real ATS would.

Evaluate these dimensions and assign a score (0-100) for each:

1. **keyword_match** — How many required/preferred keywords from the JD appear in the resume?
2. **formatting** — Is the LaTeX/text ATS-friendly (standard headings, no tables/columns that confuse parsers)?
3. **experience_relevance** — How relevant is the candidate's experience to the role?
4. **skills_alignment** — Do the listed skills match what the JD asks for?
5. **education_fit** — Does the education level/field match the requirements?
6. **quantification** — Are achievements quantified with numbers/metrics?

Return ONLY valid JSON with this exact structure:
{
  "overall_score": <int 0-100>,
  "breakdown": {
    "keyword_match": <int 0-100>,
    "formatting": <int 0-100>,
    "experience_relevance": <int 0-100>,
    "skills_alignment": <int 0-100>,
    "education_fit": <int 0-100>,
    "quantification": <int 0-100>
  },
  "matched_keywords": ["keyword1", "keyword2", ...],
  "missing_keywords": ["keyword1", "keyword2", ...],
  "strengths": ["strength1", "strength2", ...],
  "weaknesses": ["weakness1", "weakness2", ...],
  "suggestions": ["actionable suggestion 1", "actionable suggestion 2", ...],
  "summary": "A 2-3 sentence overall assessment"
}

Return ONLY valid JSON — no markdown fences, no commentary.
"""


class ATSScoringAgent(BaseAgent):
    name = "ats_scorer"
    description = "Score your resume against a job description for ATS compatibility (0-100)"
    version = "1.0.0"
    max_runs_per_hour = 10
    max_runs_per_day = 50

    async def execute(self, context: AgentContext) -> AgentResult:
        from app.repositories.job_repo import JobRepository
        from app.repositories.resume_repo import ResumeRepository
        from app.repositories.user_repo import UserRepository
        from app.services.llm_service import LLMService

        db = context.db_session
        llm = context.llm_service or LLMService()
        params = context.params

        if not await llm.is_available():
            return AgentResult(success=False, errors=["LLM API is not available"])

        user_repo = UserRepository(db)
        user = await user_repo.get_by_id(uuid.UUID(context.user_id))
        if not user:
            return AgentResult(success=False, errors=["User not found"])

        # --- Resolve resume text ---
        resume_latex: str | None = None

        resume_id = params.get("resume_id")
        if resume_id:
            resume_repo = ResumeRepository(db)
            rv = await resume_repo.get_by_id(uuid.UUID(resume_id))
            if rv:
                resume_latex = rv.latex_source
            else:
                return AgentResult(success=False, errors=["Resume version not found"])
        else:
            # Fall back to master resume
            resume_latex = user.master_resume_latex

        if not resume_latex:
            return AgentResult(success=False, errors=["No resume found. Upload or save a resume first."])

        # --- Resolve job description ---
        job_description: str | None = params.get("job_description")
        job_id = params.get("job_id")

        if not job_description and job_id:
            job_repo = JobRepository(db)
            job = await job_repo.get_by_id(uuid.UUID(job_id))
            if job:
                job_description = job.description
            else:
                return AgentResult(success=False, errors=["Job not found"])

        if not job_description:
            return AgentResult(
                success=False,
                errors=["No job description provided. Pass job_id or job_description."],
            )

        # --- Call LLM for ATS scoring ---
        prompt = (
            f"RESUME (LaTeX source):\n{resume_latex[:8000]}\n\n"
            f"JOB DESCRIPTION:\n{job_description[:6000]}"
        )

        try:
            result = await llm.generate_json(prompt, system=ATS_SCORING_SYSTEM_PROMPT)
            if not isinstance(result, dict):
                return AgentResult(success=False, errors=["LLM returned invalid format"])
        except Exception as e:
            logger.error("ATS scoring LLM call failed", error=str(e))
            return AgentResult(success=False, errors=[f"LLM error: {e}"])

        overall = result.get("overall_score", 0)
        logger.info(
            "ATS scoring complete",
            overall_score=overall,
            matched=len(result.get("matched_keywords", [])),
            missing=len(result.get("missing_keywords", [])),
        )

        return AgentResult(
            success=True,
            data=result,
            items_processed=1,
        )
