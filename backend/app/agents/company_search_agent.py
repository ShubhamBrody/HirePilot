"""
Company Search Agent

Scrapes target company career pages, scores jobs, and auto-applies
when match score exceeds the user's threshold.
Each company gets independent scraping with error tracking and backoff.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.core.logging import get_logger

logger = get_logger(__name__)


class CompanySearchAgent(BaseAgent):
    name = "company_search"
    description = "Search target company career pages for matching jobs and auto-apply"
    max_runs_per_hour = 10
    max_runs_per_day = 50

    async def execute(self, context: AgentContext) -> AgentResult:
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.models.job import JobListing, JobSource
        from app.models.scraping_log import CompanyScrapingLog, ScrapingRunStatus
        from app.models.target_company import ScrapeStatus
        from app.repositories.job_repo import JobRepository
        from app.repositories.target_company_repo import (
            ScrapingLogRepository,
            TargetCompanyRepository,
        )
        from app.repositories.user_repo import UserRepository
        from app.services.career_discovery import CareerPageDiscoveryService
        from app.services.job_scraper import CompanyCareerScraper
        from app.services.llm_service import LLMService
        from app.services.scraping_intelligence import ScrapingIntelligence
        from app.schemas.job import JobSearchFilters

        db: AsyncSession = context.db_session
        llm = context.llm_service or LLMService()
        user_repo = UserRepository(db)
        job_repo = JobRepository(db)
        tc_repo = TargetCompanyRepository(db)
        log_repo = ScrapingLogRepository(db)

        user = await user_repo.get_by_id(uuid.UUID(context.user_id))
        if not user:
            return AgentResult(success=False, errors=["User not found"])

        if not user.company_search_enabled:
            return AgentResult(success=False, errors=["Company search is disabled"])

        # Get target companies to scrape
        target_company_id = context.params.get("target_company_id")
        if target_company_id:
            company = await tc_repo.get_by_id(uuid.UUID(target_company_id))
            companies = [company] if company and company.is_enabled else []
        else:
            companies = await tc_repo.get_due_for_scraping(user.id)

        if not companies:
            return AgentResult(
                success=True,
                data={"message": "No companies due for scraping"},
                items_processed=0,
            )

        total_jobs_found = 0
        total_jobs_saved = 0
        total_auto_applied = 0
        company_results = []

        for tc in companies:
            # Check backoff based on recent failures
            recent_failures = await log_repo.get_recent_failures(tc.id, hours=24)
            should_skip, wait_hours = ScrapingIntelligence.should_backoff(recent_failures)
            if should_skip:
                logger.info(
                    "Skipping company due to backoff",
                    company=tc.company_name,
                    recent_failures=recent_failures,
                    wait_hours=wait_hours,
                )
                company_results.append({
                    "company": tc.company_name,
                    "status": "skipped_backoff",
                    "recent_failures": recent_failures,
                })
                continue

            # Create scraping log
            scrape_log = CompanyScrapingLog(
                id=uuid.uuid4(),
                target_company_id=tc.id,
                user_id=user.id,
                started_at=datetime.now(UTC),
                status=ScrapingRunStatus.RUNNING,
                page_url_used=tc.career_page_url,
            )
            db.add(scrape_log)
            await db.flush()

            try:
                # Step 1: Discover career URL if missing
                if not tc.career_page_url:
                    logger.info("Discovering career URL", company=tc.company_name)
                    discovery = CareerPageDiscoveryService(llm)
                    result = await discovery.discover_career_url(tc.company_name)
                    if result.get("career_url"):
                        tc.career_page_url = result["career_url"]
                        from app.models.target_company import URLDiscoveryMethod
                        tc.url_discovery_method = URLDiscoveryMethod.AI_DISCOVERED
                        tc.url_verified = False
                        await db.flush()
                        scrape_log.page_url_used = tc.career_page_url
                    else:
                        raise ValueError(f"Could not discover career URL for {tc.company_name}")

                # Step 2: Scrape career page
                strategy = ScrapingIntelligence.parse_strategy(tc.scrape_strategy)
                scraper = CompanyCareerScraper(
                    career_url=tc.career_page_url,
                    company_name=tc.company_name,
                    strategy=strategy,
                )
                filters = JobSearchFilters(max_results=50)
                raw_jobs = await scraper.scrape(filters, context.user_id)

                # Step 3: Deduplicate and save
                jobs_saved = 0
                for raw in raw_jobs:
                    source_url = raw.get("source_url", "")
                    if not source_url:
                        continue
                    existing = await job_repo.get_by_source_url(source_url)
                    if existing:
                        continue

                    # Create job listing
                    job = JobListing(
                        id=uuid.uuid4(),
                        user_id=user.id,
                        title=raw.get("title", "Unknown"),
                        company=tc.company_name,
                        location=raw.get("location"),
                        description=raw.get("description", ""),
                        requirements=raw.get("requirements"),
                        source=JobSource.COMPANY_CAREER,
                        source_url=source_url,
                        technologies=raw.get("technologies"),
                        discovered_at=datetime.now(UTC),
                        is_active=True,
                    )
                    db.add(job)
                    jobs_saved += 1

                    # Step 4: Score job against resume
                    if user.master_resume_latex and raw.get("description"):
                        try:
                            score_result = await llm.compute_fit_score(
                                user.master_resume_latex,
                                raw["description"],
                            )
                            if isinstance(score_result, dict):
                                job.match_score = score_result.get("match_score")
                                job.match_reasoning = json.dumps(score_result)
                        except Exception as e:
                            logger.warning("Match scoring failed", error=str(e))

                    # Step 5: Auto-apply if above threshold
                    if (
                        user.auto_apply_threshold
                        and job.match_score
                        and job.match_score >= user.auto_apply_threshold
                    ):
                        try:
                            await self._auto_apply(db, user, job, llm)
                            total_auto_applied += 1
                        except Exception as e:
                            logger.warning("Auto-apply failed", job_id=str(job.id), error=str(e))

                await db.flush()

                # Update successful scrape status
                scrape_log.status = ScrapingRunStatus.SUCCESS
                scrape_log.jobs_found = len(raw_jobs)
                scrape_log.new_jobs_saved = jobs_saved
                scrape_log.completed_at = datetime.now(UTC)
                scrape_log.duration_seconds = (
                    scrape_log.completed_at - scrape_log.started_at
                ).total_seconds()

                await tc_repo.update_scrape_result(
                    tc,
                    status=ScrapeStatus.SUCCESS,
                    jobs_found=jobs_saved,
                )

                # Mark URL as verified on first successful scrape with jobs
                if not tc.url_verified and len(raw_jobs) > 0:
                    from app.models.target_company import URLDiscoveryMethod
                    tc.url_verified = True
                    tc.url_discovery_method = URLDiscoveryMethod.VERIFIED

                total_jobs_found += len(raw_jobs)
                total_jobs_saved += jobs_saved

                company_results.append({
                    "company": tc.company_name,
                    "status": "success",
                    "jobs_found": len(raw_jobs),
                    "jobs_saved": jobs_saved,
                })

            except Exception as e:
                error_str = str(e)
                error_type = ScrapingIntelligence.classify_error(e)

                scrape_log.status = ScrapingRunStatus.FAILED
                scrape_log.error_message = error_str[:1000]
                scrape_log.error_type = error_type
                scrape_log.completed_at = datetime.now(UTC)
                scrape_log.duration_seconds = (
                    scrape_log.completed_at - scrape_log.started_at
                ).total_seconds()

                await tc_repo.update_scrape_result(
                    tc,
                    status=ScrapeStatus.FAILED,
                    error=error_str[:500],
                )

                company_results.append({
                    "company": tc.company_name,
                    "status": "failed",
                    "error": error_str[:200],
                    "error_type": error_type,
                })

                logger.error(
                    "Company scrape failed",
                    company=tc.company_name,
                    error=error_str[:200],
                    error_type=error_type,
                )

        await db.commit()

        return AgentResult(
            success=True,
            data={
                "companies_processed": len(companies),
                "total_jobs_found": total_jobs_found,
                "total_jobs_saved": total_jobs_saved,
                "total_auto_applied": total_auto_applied,
                "company_results": company_results,
            },
            items_processed=total_jobs_saved,
        )

    async def _auto_apply(self, db, user, job, llm):
        """Auto-apply to a job: tailor resume, create application, queue apply task."""
        from app.models.application import Application, ApplicationMethod, ApplicationStatus
        from app.repositories.application_repo import ApplicationRepository

        app_repo = ApplicationRepository(db)

        # Check if already applied
        already_applied = await app_repo.application_exists(
            user_id=user.id,
            job_listing_id=job.id,
        )
        if already_applied:
            return

        # Tailor resume for this job
        tailored_latex = None
        if user.master_resume_latex and job.description:
            try:
                tailor_result = await llm.tailor_resume(
                    user.master_resume_latex,
                    job.description,
                    job.company,
                    job.title,
                )
                tailored_latex = tailor_result.get("tailored_latex")
            except Exception as e:
                logger.warning("Resume tailoring failed for auto-apply", error=str(e))

        # Save tailored resume version
        resume_version_id = None
        if tailored_latex:
            from app.models.resume import ResumeVersion
            resume = ResumeVersion(
                id=uuid.uuid4(),
                user_id=user.id,
                latex_source=tailored_latex,
                is_master=False,
                tailored_for_job_id=job.id,
                version_number=0,
            )
            db.add(resume)
            await db.flush()
            resume_version_id = resume.id

        # Create application record
        application = Application(
            id=uuid.uuid4(),
            user_id=user.id,
            job_listing_id=job.id,
            resume_version_id=resume_version_id,
            company=job.company,
            role=job.title,
            job_description_snapshot=job.description[:2000] if job.description else None,
            status=ApplicationStatus.DRAFT,
            method=ApplicationMethod.AUTOMATED,
            cover_letter=user.cover_letter_default,
            automation_log=json.dumps({
                "source": "company_career_auto_apply",
                "match_score": job.match_score,
                "threshold": user.auto_apply_threshold,
            }),
        )
        db.add(application)
        await db.flush()

        # Queue Selenium auto-apply task
        from app.tasks.automation import auto_apply_job
        auto_apply_job.delay(str(user.id), str(application.id), {})

        logger.info(
            "Auto-apply queued",
            company=job.company,
            role=job.title,
            match_score=job.match_score,
            application_id=str(application.id),
        )
