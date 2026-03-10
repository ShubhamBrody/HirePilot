"""
Application Repository
"""

import uuid
from datetime import datetime

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application, ApplicationStatus
from app.repositories.base import BaseRepository


class ApplicationRepository(BaseRepository[Application]):
    def __init__(self, session: AsyncSession):
        super().__init__(Application, session)

    async def get_user_applications(
        self,
        user_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 20,
        status: ApplicationStatus | None = None,
        company: str | None = None,
        role: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[Application]:
        """Get user's applications with filters."""
        query = select(Application).where(Application.user_id == user_id)
        if status:
            query = query.where(Application.status == status)
        if company:
            query = query.where(Application.company.ilike(f"%{company}%"))
        if role:
            query = query.where(Application.role.ilike(f"%{role}%"))
        if date_from:
            query = query.where(Application.created_at >= date_from)
        if date_to:
            query = query.where(Application.created_at <= date_to)
        query = query.order_by(desc(Application.updated_at)).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count_user_applications(
        self, user_id: uuid.UUID, status: ApplicationStatus | None = None
    ) -> int:
        """Count user's applications, optionally filtered by status."""
        query = select(func.count()).select_from(Application).where(
            Application.user_id == user_id
        )
        if status:
            query = query.where(Application.status == status)
        result = await self.session.execute(query)
        return result.scalar_one()

    async def get_status_counts(self, user_id: uuid.UUID) -> dict[str, int]:
        """Get count of applications per status."""
        query = (
            select(Application.status, func.count())
            .where(Application.user_id == user_id)
            .group_by(Application.status)
        )
        result = await self.session.execute(query)
        return {row[0].value: row[1] for row in result.all()}

    async def application_exists(
        self, user_id: uuid.UUID, job_listing_id: uuid.UUID
    ) -> bool:
        """Check if user already applied to this job."""
        query = (
            select(func.count())
            .select_from(Application)
            .where(Application.user_id == user_id)
            .where(Application.job_listing_id == job_listing_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one() > 0
