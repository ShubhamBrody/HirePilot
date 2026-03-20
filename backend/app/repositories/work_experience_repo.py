"""
Work Experience Repository — CRUD for work experience entries.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.work_experience import WorkExperience
from app.repositories.base import BaseRepository


class WorkExperienceRepository(BaseRepository[WorkExperience]):
    def __init__(self, session: AsyncSession):
        super().__init__(WorkExperience, session)

    async def get_by_user(self, user_id: uuid.UUID) -> list[WorkExperience]:
        query = (
            select(WorkExperience)
            .where(WorkExperience.user_id == user_id)
            .order_by(WorkExperience.sort_order)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def delete_all_for_user(self, user_id: uuid.UUID) -> int:
        entries = await self.get_by_user(user_id)
        for entry in entries:
            await self.session.delete(entry)
        await self.session.flush()
        return len(entries)
