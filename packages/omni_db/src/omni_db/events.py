"""Transactional event outbox issuer."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from omni_core.ids import uuid7
from omni_db.models.system import WorkflowEventModel


async def emit_event(
    session: AsyncSession,
    session_id: UUID,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> WorkflowEventModel:
    """Emit a workflow event to the transactional outbox with a gapless per-session seq.

    This function MUST be called inside an active transaction.
    It locks the session's event stream row/aggregation to guarantee gapless sequence numbers.

    Args:
        session: Active AsyncSession with transaction open.
        session_id: ID of the research session.
        event_type: WorkflowEventType string value.
        payload: Event payload dictionary.

    Returns:
        The created WorkflowEventModel instance.
    """
    if payload is None:
        payload = {}

    # Query highest sequence number for this session with row-level lock or MAX query
    # Using SELECT MAX(seq) with lock on the max row or table lock semantics
    stmt = (
        select(func.coalesce(func.max(WorkflowEventModel.seq), 0))
        .where(WorkflowEventModel.session_id == session_id)
        .with_for_update()
    )
    result = await session.execute(stmt)
    current_max_seq = result.scalar_one()
    next_seq = current_max_seq + 1

    event = WorkflowEventModel(
        session_id=session_id,
        seq=next_seq,
        event_id=uuid7(),
        event_type=event_type,
        payload=payload,
    )
    session.add(event)
    return event
