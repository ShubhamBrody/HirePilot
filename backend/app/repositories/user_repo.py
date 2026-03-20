"""
User Repository
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession):
        super().__init__(User, session)

    async def get_by_email(self, email: str) -> User | None:
        """Fetch user by email address."""
        query = select(User).where(User.email == email)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """Fetch user by ID."""
        return await self.session.get(User, user_id)

    async def email_exists(self, email: str) -> bool:
        """Check if an email is already registered."""
        user = await self.get_by_email(email)
        return user is not None

    async def get_active_users_with_preferences(self) -> list[User]:
        """Get all active users who have job search keywords set."""
        query = (
            select(User)
            .where(User.is_active.is_(True))
            .where(User.job_search_keywords.isnot(None))
            .where(User.job_search_keywords != "")
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
