"""
Job Search Agent

LinkedIn-first job search: tries authenticated LinkedIn scraping,
then falls back to the generic scraper orchestrator (LinkedIn public,
Indeed, Naukri). Uses LLM for salary estimation and match scoring.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.core.logging import get_logger

logger = get_logger(__name__)

SALARY_SYSTEM_PROMPT = (
    "You are a compensation analyst. Given a job description, estimate the salary. "
    "Return JSON: {\"base_low\": int, \"base_high\": int, \"stocks_yearly\": int, "
    "\"bonus_percent\": int, \"take_home_low\": int, \"take_home_high\": int, "
    "\"currency\": \"USD\", \"notes\": \"brief explanation\"}. "
    "If not enough info, make a reasonable estimate for the role/location. "
    "Return ONLY valid JSON."
)


class JobSearchAgent(BaseAgent):
    name = "job_search"
    description = "Search LinkedIn (authenticated), Indeed, Naukri for jobs matching your preferences"
    max_runs_per_hour = 2
    max_runs_per_day = 12

    async def _save_job(self, raw, user, job_repo, llm, db):
        """Process and save a single raw job dict to the DB."""
        from app.models.job import JobListing, JobSource

        source_url = raw.get("source_url") or raw.get("url", "")
        if not source_url:
            return False
        existing = await job_repo.get_by_source_url(source_url)
        if existing:
            return False

        description = raw.get("description", "")

        salary_breakdown = {}
        if description and await llm.is_available():
            try:
                prompt = (
                    f"Job: {raw.get('title', '')} at {raw.get('company', '')} "
                    f"in {raw.get('location', '')}.\n\nDescription:\n{description[:3000]}"
                )
                salary_breakdown = await llm.generate_json(prompt, system=SALARY_SYSTEM_PROMPT)
                if not isinstance(salary_breakdown, dict):
                    salary_breakdown = {}
            except Exception:
                salary_breakdown = {}

        match_score = None
        if description and user.master_resume_latex and await llm.is_available():
            try:
                match_score = await llm.compute_fit_score(user.master_resume_latex, description)
            except Exception:
                pass

        source_str = raw.get("source", "other").lower()
        source_enum = getattr(JobSource, source_str.upper(), JobSource.OTHER)

        job = JobListing(
            id=uuid.uuid4(),
            user_id=user.id,
            title=raw.get("title", "Unknown"),
            company=raw.get("company", "Unknown"),
            location=raw.get("location"),
            description=description,
            requirements=raw.get("requirements"),
            source=source_enum,
            source_url=source_url,
            source_job_id=raw.get("source_job_id"),
            salary_min=salary_breakdown.get("base_low") or raw.get("salary_min"),
            salary_max=salary_breakdown.get("base_high") or raw.get("salary_max"),
            salary_currency=salary_breakdown.get("currency", "USD"),
            technologies=raw.get("technologies"),
            match_score=match_score,
            estimated_salary_breakdown=json.dumps(salary_breakdown) if salary_breakdown else None,
            discovered_at=datetime.now(UTC),
        )
        await job_repo.create(job)
        return True

    async def execute(self, context: AgentContext) -> AgentResult:
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.agents.linkedin_helper import linkedin_search_jobs
        from app.models.job import JobSource
        from app.repositories.job_repo import JobRepository
        from app.repositories.user_repo import UserRepository
        from app.services.job_scraper import JobScraperOrchestrator
        from app.services.llm_service import LLMService

        db: AsyncSession = context.db_session
        llm = context.llm_service or LLMService()
        user_repo = UserRepository(db)
        job_repo = JobRepository(db)

        user = await user_repo.get_by_id(uuid.UUID(context.user_id))
        if not user:
            return AgentResult(success=False, errors=["User not found"])

        keywords = user.job_search_keywords or ""
        location = user.preferred_location or ""
        target_roles_raw = user.target_roles or "[]"
        try:
            target_roles = json.loads(target_roles_raw)
        except (json.JSONDecodeError, TypeError):
            target_roles = [target_roles_raw] if target_roles_raw else []

        if not keywords and not target_roles:
            return AgentResult(success=False, errors=["No job search preferences set"])

        search_terms = keywords or ", ".join(target_roles)

        all_raw_jobs: list[dict] = []
        linkedin_ok = False

        # ── Step 1: LinkedIn authenticated search (primary) ──
        logger.info("Trying LinkedIn authenticated job search", keywords=search_terms)
        li_result = await linkedin_search_jobs(db, context.user_id, search_terms, location, max_results=25)

        if li_result.get("success") and li_result.get("jobs"):
            linkedin_ok = True
            for j in li_result["jobs"]:
                j.setdefault("source", "linkedin")
                all_raw_jobs.append(j)
            logger.info("LinkedIn returned jobs", count=len(li_result["jobs"]))
        else:
            reason = li_result.get("error", "unknown")
            logger.warning("LinkedIn auth search unavailable, using fallback scrapers", reason=reason)

        # ── Step 2: Fallback scrapers (Indeed, Naukri, public LinkedIn) ──
        params = context.params
        source_names = params.get("sources", ["indeed", "naukri"] if linkedin_ok else ["linkedin", "indeed", "naukri"])

        from app.models.job import JobSource as JS
        from app.schemas.job import JobSearchFilters

        source_enums = []
        for s in source_names:
            if linkedin_ok and s == "linkedin":
                continue  # Skip public LinkedIn scraper if we already got authenticated results
            src = getattr(JS, s.upper(), None)
            if src:
                source_enums.append(src)

        if source_enums:
            orchestrator = JobScraperOrchestrator()
            filters = JobSearchFilters(role=search_terms, location=location or None)
            fallback_jobs = await orchestrator.scrape_all(
                filters=filters, user_id=context.user_id, sources=source_enums
            )
            all_raw_jobs.extend(fallback_jobs)

        # ── Step 3: Deduplicate and save ──
        saved_count = 0
        for raw in all_raw_jobs:
            saved = await self._save_job(raw, user, job_repo, llm, db)
            if saved:
                saved_count += 1

        await db.commit()

        return AgentResult(
            success=True,
            data={
                "jobs_found": len(all_raw_jobs),
                "jobs_saved": saved_count,
                "linkedin_authenticated": linkedin_ok,
            },
            items_processed=saved_count,
        )
