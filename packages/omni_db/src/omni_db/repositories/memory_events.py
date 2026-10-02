"""Memory events repository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from omni_db.models.memory_events import MemoryEventModel
from omni_db.repositories.base import BaseRepository


class MemoryRepository(BaseRepository[MemoryEventModel]):
    """Repository for T2 episodic memory ledger."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, MemoryEventModel)

    async def get_session_memory(self, session_id: UUID) -> list[MemoryEventModel]:
        """Fetch all memory events for a session in order of creation."""
        stmt = (
            select(MemoryEventModel)
            .where(MemoryEventModel.session_id == session_id)
            .order_by(MemoryEventModel.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
