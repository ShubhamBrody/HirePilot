"""
Recruiter Search Agent

LinkedIn-first recruiter discovery: uses authenticated LinkedIn people
search to find real recruiters at target companies. Falls back to
LLM-generated profiles when LinkedIn is unavailable.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.core.logging import get_logger

logger = get_logger(__name__)


class RecruiterSearchAgent(BaseAgent):
    name = "recruiter_search"
    description = "Find recruiters and hiring managers at target companies via LinkedIn"
    max_runs_per_hour = 4
    max_runs_per_day = 24

    async def execute(self, context: AgentContext) -> AgentResult:
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.agents.linkedin_helper import linkedin_search_people
        from app.models.recruiter import ConnectionStatus, Recruiter
        from app.repositories.recruiter_repo import RecruiterRepository
        from app.repositories.user_repo import UserRepository

        db: AsyncSession = context.db_session
        company = context.params.get("company", "")
        role = context.params.get("role", "Software Engineer")

        # If no company specified, try to pick from saved jobs
        if not company:
            from app.repositories.job_repo import JobRepository

            job_repo = JobRepository(db)
            user_repo = UserRepository(db)
            user = await user_repo.get_by_id(uuid.UUID(context.user_id))
            if user:
                jobs = await job_repo.get_user_jobs(user.id, limit=10)
                companies = list({j.company for j in jobs if j.company})
                if companies:
                    company = companies[0]
                    logger.info("Auto-selected company from saved jobs", company=company)

        if not company:
            return AgentResult(success=False, errors=["No company specified and no saved jobs to pick from"])

        all_profiles: list[dict] = []
        linkedin_ok = False

        # ── Step 1: LinkedIn authenticated people search ──
        logger.info("Trying LinkedIn people search", company=company, role=role)
        li_result = await linkedin_search_people(db, context.user_id, company, max_results=10)

        if li_result.get("success") and li_result.get("people"):
            linkedin_ok = True
            for p in li_result["people"]:
                all_profiles.append({
                    "id": uuid.uuid4(),
                    "name": p.get("name", "Unknown"),
                    "title": p.get("title"),
                    "company": p.get("company", company),
                    "email": p.get("email"),
                    "linkedin_url": p.get("linkedin_url"),
                })
            logger.info("LinkedIn returned people", count=len(li_result["people"]))
        else:
            reason = li_result.get("error", "unknown")
            logger.warning("LinkedIn people search unavailable, falling back to LLM", reason=reason)

        # ── Step 2: LLM verification — filter to actual recruiters ──
        if all_profiles:
            from app.services.llm_service import LLMService
            llm = LLMService()
            try:
                all_profiles = await llm.verify_recruiter_profiles(
                    all_profiles, company, role,
                )
            except Exception as e:
                logger.warning("LLM recruiter verification failed", error=str(e))

        # ── Step 3: Save to DB ──
        repo = RecruiterRepository(db)
        saved_count = 0
        for p in all_profiles:
            linkedin_url = p.get("linkedin_url")
            if linkedin_url:
                existing = await repo.get_by_linkedin_url(linkedin_url)
                if existing:
                    continue

            recruiter = Recruiter(
                id=p.get("id", uuid.uuid4()),
                user_id=uuid.UUID(context.user_id),
                name=p.get("name", "Unknown"),
                title=p.get("title"),
                company=p.get("company", company),
                email=p.get("email"),
                linkedin_url=linkedin_url,
                connection_status=ConnectionStatus.NOT_CONNECTED,
                platform="linkedin",
                discovered_at=datetime.now(UTC),
            )
            await repo.create(recruiter)
            saved_count += 1

        await db.commit()

        return AgentResult(
            success=True,
            data={
                "company": company,
                "profiles_found": len(all_profiles),
                "saved": saved_count,
                "linkedin_authenticated": linkedin_ok,
            },
            items_processed=saved_count,
        )
