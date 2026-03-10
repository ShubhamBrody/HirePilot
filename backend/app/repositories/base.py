"""
Base Repository

Generic async CRUD repository using SQLAlchemy 2.0.
All domain repositories inherit from this.
"""

import uuid
from typing import Any, Generic, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Generic async CRUD repository."""

    def __init__(self, model: type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session

    async def get_by_id(self, entity_id: uuid.UUID) -> ModelType | None:
        """Fetch a single entity by primary key."""
        return await self.session.get(self.model, entity_id)

    async def get_all(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: dict[str, Any] | None = None,
        order_by: Any | None = None,
    ) -> list[ModelType]:
        """Fetch multiple entities with optional filters and pagination."""
        query = select(self.model)
        if filters:
            for key, value in filters.items():
                if value is not None and hasattr(self.model, key):
                    query = query.where(getattr(self.model, key) == value)
        if order_by is not None:
            query = query.order_by(order_by)
        query = query.offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        """Count entities matching the given filters."""
        query = select(func.count()).select_from(self.model)
        if filters:
            for key, value in filters.items():
                if value is not None and hasattr(self.model, key):
                    query = query.where(getattr(self.model, key) == value)
        result = await self.session.execute(query)
        return result.scalar_one()

    async def create(self, entity: ModelType) -> ModelType:
        """Persist a new entity."""
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def update(self, entity: ModelType, data: dict[str, Any]) -> ModelType:
        """Update an entity with the given data dict."""
        for key, value in data.items():
            if hasattr(entity, key):
                setattr(entity, key, value)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def delete(self, entity: ModelType) -> None:
        """Delete an entity."""
        await self.session.delete(entity)
        await self.session.flush()

    async def execute_query(self, query: Select) -> list[ModelType]:  # type: ignore[type-arg]
        """Execute a custom SQLAlchemy select query."""
        result = await self.session.execute(query)
        return list(result.scalars().all())
