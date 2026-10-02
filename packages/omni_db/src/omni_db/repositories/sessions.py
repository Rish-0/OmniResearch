"""Session repository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from omni_db.models.research_session import ResearchSession
from omni_db.repositories.base import BaseRepository


class SessionRepository(BaseRepository[ResearchSession]):
    """Repository for managing research sessions."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ResearchSession)

    async def get_by_project(self, org_id: UUID, project_id: UUID) -> list[ResearchSession]:
        """Fetch all sessions for a project with server-side org filter."""
        stmt = select(ResearchSession).where(
            ResearchSession.org_id == org_id,
            ResearchSession.project_id == project_id,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(self, session_id: UUID, status: str) -> bool:
        """Update session status."""
        obj = await self.get_by_id(session_id)
        if not obj:
            return False
        obj.status = status
        return True
