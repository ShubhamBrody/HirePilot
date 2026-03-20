"""
Education Repository — CRUD for education entries.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.education import Education
from app.repositories.base import BaseRepository


class EducationRepository(BaseRepository[Education]):
    def __init__(self, session: AsyncSession):
        super().__init__(Education, session)

    async def get_by_user(self, user_id: uuid.UUID) -> list[Education]:
        query = (
            select(Education)
            .where(Education.user_id == user_id)
            .order_by(Education.sort_order)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def delete_all_for_user(self, user_id: uuid.UUID) -> int:
        entries = await self.get_by_user(user_id)
        for entry in entries:
            await self.session.delete(entry)
        await self.session.flush()
        return len(entries)
