"""
Resume Repository
"""

import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resume import ResumeVersion, ResumeTemplate
from app.repositories.base import BaseRepository


class ResumeRepository(BaseRepository[ResumeVersion]):
    def __init__(self, session: AsyncSession):
        super().__init__(ResumeVersion, session)

    async def get_user_resumes(
        self, user_id: uuid.UUID, *, skip: int = 0, limit: int = 50
    ) -> list[ResumeVersion]:
        """Get all resume versions for a user."""
        query = (
            select(ResumeVersion)
            .where(ResumeVersion.user_id == user_id)
            .order_by(desc(ResumeVersion.updated_at))
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_master_resume(self, user_id: uuid.UUID) -> ResumeVersion | None:
        """Get the user's master resume."""
        query = (
            select(ResumeVersion)
            .where(ResumeVersion.user_id == user_id)
            .where(ResumeVersion.is_master.is_(True))
            .order_by(desc(ResumeVersion.updated_at))
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_next_version_number(self, user_id: uuid.UUID) -> int:
        """Calculate the next version number for a user's resumes."""
        query = (
            select(ResumeVersion.version_number)
            .where(ResumeVersion.user_id == user_id)
            .order_by(desc(ResumeVersion.version_number))
            .limit(1)
        )
        result = await self.session.execute(query)
        current = result.scalar_one_or_none()
        return (current or 0) + 1

    async def count_user_resumes(self, user_id: uuid.UUID) -> int:
        return await self.count({"user_id": user_id})


class ResumeTemplateRepository(BaseRepository[ResumeTemplate]):
    def __init__(self, session: AsyncSession):
        super().__init__(ResumeTemplate, session)

    async def get_active_templates(self) -> list[ResumeTemplate]:
        """Get all active resume templates."""
        query = (
            select(ResumeTemplate)
            .where(ResumeTemplate.is_active.is_(True))
            .order_by(ResumeTemplate.name)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_category(self, category: str) -> list[ResumeTemplate]:
        query = (
            select(ResumeTemplate)
            .where(ResumeTemplate.category == category)
            .where(ResumeTemplate.is_active.is_(True))
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
