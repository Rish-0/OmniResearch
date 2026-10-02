"""Task and TaskAttempt repository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from omni_db.models.research_session import Task, TaskAttempt
from omni_db.repositories.base import BaseRepository


class TaskRepository(BaseRepository[Task]):
    """Repository for tasks and execution attempts."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Task)

    async def get_session_tasks(self, session_id: UUID) -> list[Task]:
        """Fetch all tasks for a research session."""
        stmt = select(Task).where(Task.session_id == session_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_attempt(self, attempt: TaskAttempt) -> TaskAttempt:
        """Record a task execution attempt."""
        self.session.add(attempt)
        return attempt

    async def get_attempt_by_key(self, idempotency_key: str) -> TaskAttempt | None:
        """Fetch an attempt by idempotency key."""
        stmt = select(TaskAttempt).where(TaskAttempt.idempotency_key == idempotency_key)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
