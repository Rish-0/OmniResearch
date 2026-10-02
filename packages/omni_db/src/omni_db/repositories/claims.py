"""Claim and evidence repository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from omni_db.models.analysis import Claim, ClaimEvidence
from omni_db.repositories.base import BaseRepository


class ClaimRepository(BaseRepository[Claim]):
    """Repository for managing claims and linked evidence."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Claim)

    async def get_claims_for_session(self, session_id: UUID) -> list[Claim]:
        """Fetch all claims for a session."""
        stmt = select(Claim).where(Claim.session_id == session_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add_evidence_link(self, link: ClaimEvidence) -> ClaimEvidence:
        """Link evidence to a claim."""
        self.session.add(link)
        return link

    async def get_claim_evidence(self, claim_id: UUID) -> list[ClaimEvidence]:
        """Get all evidence items linked to a claim."""
        stmt = select(ClaimEvidence).where(ClaimEvidence.claim_id == claim_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
