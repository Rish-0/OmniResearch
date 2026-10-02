"""Event outbox repository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from omni_db.models.system import WorkflowEventModel


class EventRepository:
    """Repository for querying the workflow outbox events."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_events_since(
        self, session_id: UUID, since_seq: int = 0
    ) -> list[WorkflowEventModel]:
        """Fetch workflow events for a session starting after since_seq (for SSE replay)."""
        stmt = (
            select(WorkflowEventModel)
            .where(
                WorkflowEventModel.session_id == session_id,
                WorkflowEventModel.seq > since_seq,
            )
            .order_by(WorkflowEventModel.seq.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
