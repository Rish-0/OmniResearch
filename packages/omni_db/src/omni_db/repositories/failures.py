"""Failure record repository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from omni_db.models.memory_events import Failure
from omni_db.repositories.base import BaseRepository


class FailureRepository(BaseRepository[Failure]):
    """Repository for querying recorded failures and checking fingerprints."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Failure)

    async def get_by_fingerprint(self, session_id: UUID, fingerprint: str) -> Failure | None:
        """Check if a failure with the given fingerprint already occurred in this session."""
        stmt = select(Failure).where(
            Failure.session_id == session_id,
            Failure.fingerprint == fingerprint,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
