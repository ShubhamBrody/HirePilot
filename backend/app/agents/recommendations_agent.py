"""
Recommendations Agent

Analyzes scraped job descriptions to provide skill insights,
trending technologies, and career recommendations for the user's target role.
"""

from __future__ import annotations

import json
import uuid

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.core.logging import get_logger

logger = get_logger(__name__)

RECOMMENDATIONS_SYSTEM = (
    "You are a career advisor. Given a list of job descriptions for a target role, "
    "analyze them and return JSON: "
    "{\"top_skills\": [{\"skill\": str, \"frequency\": int, \"priority\": \"high|medium|low\"}], "
    "\"trending_technologies\": [str], "
    "\"career_advice\": [str], "
    "\"skill_gaps\": [{\"skill\": str, \"importance\": \"critical|important|nice_to_have\"}], "
    "\"learning_path\": [str]}. "
    "Return ONLY valid JSON."
)


class RecommendationsAgent(BaseAgent):
    name = "recommendations"
    description = "Analyze job market trends and recommend skills to learn for your target role"
    max_runs_per_hour = 4
    max_runs_per_day = 12

    async def execute(self, context: AgentContext) -> AgentResult:
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.repositories.job_repo import JobRepository
        from app.repositories.user_repo import UserRepository
        from app.services.llm_service import LLMService

        db: AsyncSession = context.db_session
        llm = context.llm_service or LLMService()

        user_repo = UserRepository(db)
        job_repo = JobRepository(db)

        user = await user_repo.get_by_id(uuid.UUID(context.user_id))
        if not user:
            return AgentResult(success=False, errors=["User not found"])

        target_roles_raw = user.target_roles or "[]"
        try:
            target_roles = json.loads(target_roles_raw)
        except (json.JSONDecodeError, TypeError):
            target_roles = []

        role_str = ", ".join(target_roles) if target_roles else "Software Engineer"
        user_skills = user.skills or "[]"

        # Get recent job descriptions
        jobs = await job_repo.get_user_jobs(user.id, skip=0, limit=50)
        if not jobs:
            return AgentResult(
                success=False,
                errors=["No jobs found. Run the Job Search agent first."],
            )

        descriptions = []
        for job in jobs[:30]:
            desc = f"Title: {job.title}\nCompany: {job.company}\n"
            if job.description:
                desc += job.description[:1000]
            descriptions.append(desc)

        combined = "\n---\n".join(descriptions)

        prompt = (
            f"Target role: {role_str}\n"
            f"User's current skills: {user_skills}\n\n"
            f"Job descriptions ({len(descriptions)} jobs):\n{combined[:10000]}\n\n"
            "Analyze these jobs and provide recommendations."
        )

        try:
            result = await llm.generate_json(prompt, system=RECOMMENDATIONS_SYSTEM)
            if not isinstance(result, dict):
                result = {"raw": str(result)}
        except Exception as e:
            return AgentResult(success=False, errors=[f"LLM analysis failed: {e}"])

        result["target_role"] = role_str
        result["jobs_analyzed"] = len(descriptions)

        return AgentResult(
            success=True,
            data=result,
            items_processed=len(descriptions),
        )
