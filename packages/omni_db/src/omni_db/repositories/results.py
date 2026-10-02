"""Experiment results repository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from omni_db.models.experiments import ExperimentRun, Result
from omni_db.repositories.base import BaseRepository


class ResultRepository(BaseRepository[Result]):
    """Repository for querying experiment runs and metric results."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Result)

    async def get_results_for_run(self, run_id: UUID) -> list[Result]:
        """Fetch all numeric metric results for a run."""
        stmt = select(Result).where(Result.run_id == run_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_run_with_experiment(self, run_id: UUID) -> ExperimentRun | None:
        """Fetch an experiment run by ID."""
        stmt = select(ExperimentRun).where(ExperimentRun.id == run_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
