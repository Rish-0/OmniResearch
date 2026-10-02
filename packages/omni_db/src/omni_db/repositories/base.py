"""Base repository class."""

from __future__ import annotations

from typing import TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from omni_db.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository[ModelT: Base]:
    """Base repository for CRUD operations."""

    def __init__(self, session: AsyncSession, model_cls: type[ModelT]) -> None:
        self.session = session
        self.model_cls = model_cls

    async def get_by_id(self, entity_id: UUID) -> ModelT | None:
        """Fetch entity by primary key."""
        result = await self.session.execute(
            select(self.model_cls).where(self.model_cls.id == entity_id)  # type: ignore[attr-defined]
        )
        return result.scalar_one_or_none()

    async def create(self, entity: ModelT) -> ModelT:
        """Add and return entity."""
        self.session.add(entity)
        return entity
