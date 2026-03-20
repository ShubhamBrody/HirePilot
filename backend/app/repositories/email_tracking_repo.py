"""
Email Tracking Repository
"""

import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email_tracking import EmailTracking
from app.repositories.base import BaseRepository


class EmailTrackingRepository(BaseRepository[EmailTracking]):
    def __init__(self, session: AsyncSession):
        super().__init__(EmailTracking, session)

    async def get_user_emails(
        self,
        user_id: uuid.UUID,
        *,
        classification: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[EmailTracking]:
        query = select(EmailTracking).where(EmailTracking.user_id == user_id)
        if classification:
            query = query.where(EmailTracking.classification == classification)
        query = query.order_by(desc(EmailTracking.email_date)).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_for_application(self, application_id: uuid.UUID) -> list[EmailTracking]:
        query = (
            select(EmailTracking)
            .where(EmailTracking.application_id == application_id)
            .order_by(desc(EmailTracking.email_date))
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
