"""
Recruiter Repository
"""

import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recruiter import ConnectionStatus, OutreachMessage, Recruiter
from app.repositories.base import BaseRepository


class RecruiterRepository(BaseRepository[Recruiter]):
    def __init__(self, session: AsyncSession):
        super().__init__(Recruiter, session)

    async def get_user_recruiters(
        self,
        user_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 50,
        connection_status: ConnectionStatus | None = None,
        company: str | None = None,
    ) -> list[Recruiter]:
        query = select(Recruiter).where(
            Recruiter.user_id == user_id,
            Recruiter.deleted_at.is_(None),
        )
        if connection_status:
            query = query.where(Recruiter.connection_status == connection_status)
        if company:
            query = query.where(Recruiter.company.ilike(f"%{company}%"))
        query = query.order_by(desc(Recruiter.discovered_at)).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_linkedin_url(self, linkedin_url: str) -> Recruiter | None:
        query = select(Recruiter).where(Recruiter.linkedin_url == linkedin_url)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_for_job(self, job_listing_id: uuid.UUID) -> list[Recruiter]:
        query = (
            select(Recruiter)
            .where(Recruiter.job_listing_id == job_listing_id)
            .where(Recruiter.deleted_at.is_(None))
            .order_by(Recruiter.name)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())


    async def get_pending_followups(
        self, cutoff: "datetime"
    ) -> list[tuple[Recruiter, "uuid.UUID"]]:
        """Get recruiters with pending connection status older than cutoff."""
        from datetime import datetime as dt
        query = (
            select(Recruiter)
            .where(Recruiter.connection_status == ConnectionStatus.PENDING)
            .where(Recruiter.discovered_at <= cutoff)
        )
        result = await self.session.execute(query)
        recruiters = list(result.scalars().all())
        return [(r, r.user_id) for r in recruiters]

    async def delete_by_company(
        self, user_id: uuid.UUID, company: str
    ) -> int:
        """Delete all recruiters for a user+company. Returns count deleted."""
        from sqlalchemy import delete, func
        stmt = (
            delete(Recruiter)
            .where(Recruiter.user_id == user_id)
            .where(func.lower(Recruiter.company) == company.lower())
        )
        result = await self.session.execute(stmt)
        return result.rowcount


class OutreachMessageRepository(BaseRepository[OutreachMessage]):
    def __init__(self, session: AsyncSession):
        super().__init__(OutreachMessage, session)

    async def get_messages_for_recruiter(
        self, recruiter_id: uuid.UUID
    ) -> list[OutreachMessage]:
        query = (
            select(OutreachMessage)
            .where(OutreachMessage.recruiter_id == recruiter_id)
            .order_by(desc(OutreachMessage.created_at))
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_user_messages(
        self, user_id: uuid.UUID, *, skip: int = 0, limit: int = 50
    ) -> list[OutreachMessage]:
        query = (
            select(OutreachMessage)
            .where(OutreachMessage.user_id == user_id)
            .order_by(desc(OutreachMessage.created_at))
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
