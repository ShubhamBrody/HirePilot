"""
Base Repository

Generic async CRUD repository using SQLAlchemy 2.0.
All domain repositories inherit from this.
"""

import uuid
from datetime import UTC, datetime
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

    @property
    def _has_deleted_at(self) -> bool:
        return hasattr(self.model, "deleted_at")

    def _exclude_deleted(self, query: Select) -> Select:
        """Add deleted_at IS NULL filter if the model supports soft-delete."""
        if self._has_deleted_at:
            query = query.where(self.model.deleted_at.is_(None))
        return query

    async def get_by_id(self, entity_id: uuid.UUID) -> ModelType | None:
        """Fetch a single entity by primary key (excludes soft-deleted)."""
        query = select(self.model).where(self.model.id == entity_id)
        query = self._exclude_deleted(query)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

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
        query = self._exclude_deleted(query)
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
        query = self._exclude_deleted(query)
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
        """Hard-delete an entity."""
        await self.session.delete(entity)
        await self.session.flush()

    # ── Soft-delete helpers ──────────────────────────────────────────

    async def soft_delete(self, entity: ModelType) -> ModelType:
        """Mark an entity as deleted (soft-delete)."""
        entity.deleted_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def restore(self, entity: ModelType) -> ModelType:
        """Restore a soft-deleted entity."""
        entity.deleted_at = None
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def get_deleted(
        self,
        *,
        filters: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ModelType]:
        """Fetch soft-deleted entities."""
        query = select(self.model).where(self.model.deleted_at.isnot(None))
        if filters:
            for key, value in filters.items():
                if value is not None and hasattr(self.model, key):
                    query = query.where(getattr(self.model, key) == value)
        query = query.order_by(self.model.deleted_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count_deleted(self, filters: dict[str, Any] | None = None) -> int:
        """Count soft-deleted entities."""
        query = (
            select(func.count())
            .select_from(self.model)
            .where(self.model.deleted_at.isnot(None))
        )
        if filters:
            for key, value in filters.items():
                if value is not None and hasattr(self.model, key):
                    query = query.where(getattr(self.model, key) == value)
        result = await self.session.execute(query)
        return result.scalar_one()

    async def get_by_id_including_deleted(self, entity_id: uuid.UUID) -> ModelType | None:
        """Fetch an entity by ID even if soft-deleted."""
        return await self.session.get(self.model, entity_id)

    async def permanent_delete_expired(self, days: int = 20) -> int:
        """Permanently delete entities that were soft-deleted more than `days` ago."""
        from sqlalchemy import delete as sa_delete
        from datetime import timedelta

        cutoff = datetime.now(UTC) - timedelta(days=days)
        stmt = (
            sa_delete(self.model)
            .where(self.model.deleted_at.isnot(None))
            .where(self.model.deleted_at < cutoff)
        )
        result = await self.session.execute(stmt)
        return result.rowcount

    async def execute_query(self, query: Select) -> list[ModelType]:  # type: ignore[type-arg]
        """Execute a custom SQLAlchemy select query."""
        result = await self.session.execute(query)
        return list(result.scalars().all())
