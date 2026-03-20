"""
Agent Execution Repository
"""

import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_execution import AgentExecution
from app.repositories.base import BaseRepository


class AgentExecutionRepository(BaseRepository[AgentExecution]):
    def __init__(self, session: AsyncSession):
        super().__init__(AgentExecution, session)

    async def get_user_executions(
        self,
        user_id: uuid.UUID,
        *,
        agent_name: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[AgentExecution]:
        query = select(AgentExecution).where(AgentExecution.user_id == user_id)
        if agent_name:
            query = query.where(AgentExecution.agent_name == agent_name)
        query = query.order_by(desc(AgentExecution.created_at)).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_recent(self, user_id: uuid.UUID, limit: int = 20) -> list[AgentExecution]:
        query = (
            select(AgentExecution)
            .where(AgentExecution.user_id == user_id)
            .order_by(desc(AgentExecution.created_at))
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
