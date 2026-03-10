"""
Audit Log Repository
"""

import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    def __init__(self, session: AsyncSession):
        super().__init__(AuditLog, session)

    async def log_action(
        self,
        user_id: uuid.UUID,
        action: str,
        module: str,
        *,
        entity_type: str | None = None,
        entity_id: str | None = None,
        details: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        status: str = "success",
        error_message: str | None = None,
    ) -> AuditLog:
        """Create an audit log entry."""
        log = AuditLog(
            user_id=user_id,
            action=action,
            module=module,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            status=status,
            error_message=error_message,
        )
        return await self.create(log)

    async def get_user_logs(
        self,
        user_id: uuid.UUID,
        *,
        module: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AuditLog]:
        query = (
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
        )
        if module:
            query = query.where(AuditLog.module == module)
        query = query.order_by(desc(AuditLog.created_at)).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())
