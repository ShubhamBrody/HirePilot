"""
Job Repository
"""

import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import JobListing, JobSource
from app.repositories.base import BaseRepository


class JobRepository(BaseRepository[JobListing]):
    def __init__(self, session: AsyncSession):
        super().__init__(JobListing, session)

    async def get_user_jobs(
        self,
        user_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 50,
        source: JobSource | None = None,
        company: str | None = None,
        is_active: bool = True,
    ) -> list[JobListing]:
        """Fetch jobs for a specific user with optional filters."""
        query = (
            select(JobListing)
            .where(JobListing.user_id == user_id)
            .where(JobListing.is_active == is_active)
        )
        if source:
            query = query.where(JobListing.source == source)
        if company:
            query = query.where(JobListing.company.ilike(f"%{company}%"))
        query = query.order_by(desc(JobListing.discovered_at)).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_source_url(self, source_url: str) -> JobListing | None:
        """Check if a job with this source URL already exists (dedup)."""
        query = select(JobListing).where(JobListing.source_url == source_url)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_jobs_by_match_score(
        self, user_id: uuid.UUID, *, min_score: float = 0.0, limit: int = 20
    ) -> list[JobListing]:
        """Fetch jobs ordered by AI match score."""
        query = (
            select(JobListing)
            .where(JobListing.user_id == user_id)
            .where(JobListing.match_score.isnot(None))
            .where(JobListing.match_score >= min_score)
            .order_by(desc(JobListing.match_score))
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count_user_jobs(self, user_id: uuid.UUID) -> int:
        """Count total jobs for a user."""
        return await self.count({"user_id": user_id})
