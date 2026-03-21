"""
Target Company Repository

Async CRUD for target companies and scraping logs with schedule-aware queries.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scraping_log import CompanyScrapingLog, ScrapingRunStatus
from app.models.target_company import ScrapeStatus, TargetCompany
from app.repositories.base import BaseRepository


class TargetCompanyRepository(BaseRepository[TargetCompany]):
    def __init__(self, session: AsyncSession):
        super().__init__(TargetCompany, session)

    async def get_user_companies(
        self,
        user_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        enabled_only: bool = False,
    ) -> list[TargetCompany]:
        query = (
            select(TargetCompany)
            .where(TargetCompany.user_id == user_id)
        )
        if enabled_only:
            query = query.where(TargetCompany.is_enabled.is_(True))
        query = (
            query
            .order_by(TargetCompany.company_name)
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count_user_companies(self, user_id: uuid.UUID) -> int:
        return await self.count({"user_id": user_id})

    async def get_by_name(
        self, user_id: uuid.UUID, company_name: str
    ) -> TargetCompany | None:
        query = (
            select(TargetCompany)
            .where(TargetCompany.user_id == user_id)
            .where(func.lower(TargetCompany.company_name) == company_name.lower())
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_due_for_scraping(
        self, user_id: uuid.UUID | None = None
    ) -> list[TargetCompany]:
        """Find enabled companies that are overdue for scraping."""
        now = datetime.now(UTC)
        query = (
            select(TargetCompany)
            .where(TargetCompany.is_enabled.is_(True))
            .where(TargetCompany.career_page_url.isnot(None))
        )
        if user_id:
            query = query.where(TargetCompany.user_id == user_id)

        result = await self.session.execute(query)
        companies = list(result.scalars().all())

        # Filter in Python: those never scraped OR past their frequency window
        due = []
        for c in companies:
            if c.last_scraped_at is None:
                due.append(c)
            elif (now - c.last_scraped_at) >= timedelta(hours=c.scrape_frequency_hours):
                due.append(c)
        return due

    async def update_scrape_result(
        self,
        company: TargetCompany,
        *,
        status: ScrapeStatus,
        jobs_found: int = 0,
        error: str | None = None,
    ) -> TargetCompany:
        company.last_scraped_at = datetime.now(UTC)
        company.last_scrape_status = status
        company.last_scrape_error = error
        if status == ScrapeStatus.SUCCESS:
            company.jobs_found_total += jobs_found
        await self.session.flush()
        await self.session.refresh(company)
        return company


class ScrapingLogRepository(BaseRepository[CompanyScrapingLog]):
    def __init__(self, session: AsyncSession):
        super().__init__(CompanyScrapingLog, session)

    async def get_company_logs(
        self,
        target_company_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 20,
    ) -> list[CompanyScrapingLog]:
        query = (
            select(CompanyScrapingLog)
            .where(CompanyScrapingLog.target_company_id == target_company_id)
            .order_by(desc(CompanyScrapingLog.started_at))
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count_company_logs(self, target_company_id: uuid.UUID) -> int:
        return await self.count({"target_company_id": target_company_id})

    async def get_recent_failures(
        self, target_company_id: uuid.UUID, hours: int = 24
    ) -> int:
        """Count recent failures for backoff decisions."""
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        query = (
            select(func.count())
            .select_from(CompanyScrapingLog)
            .where(CompanyScrapingLog.target_company_id == target_company_id)
            .where(CompanyScrapingLog.status == ScrapingRunStatus.FAILED)
            .where(CompanyScrapingLog.started_at >= cutoff)
        )
        result = await self.session.execute(query)
        return result.scalar_one()
