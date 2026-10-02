"""Workflow events outbox, audit log, error log, and embedding cache models."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    ForeignKey,
    Index,
    PrimaryKeyConstraint,
    String,
    Text,
)
from sqlalchemy import (
    UUID as SQLUUID,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from omni_core.ids import uuid7
from omni_db.models.base import Base, TimestampMixin

JSON_TYPE = JSONB().with_variant(JSON(), "sqlite")


class WorkflowEventModel(Base, TimestampMixin):
    """Outbox table for session event streaming with gapless per-session sequence numbers."""

    __tablename__ = "workflow_events"

    session_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False
    )
    seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), nullable=False, default=uuid7)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False, default=dict)

    __table_args__ = (
        PrimaryKeyConstraint("session_id", "seq", name="pk_workflow_events"),
        Index("idx_workflow_events_session_seq", "session_id", "seq"),
    )


class AuditLog(Base, TimestampMixin):
    """Append-only audit log for system and security actions."""

    __tablename__ = "audit_log"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid7)
    user_id: Mapped[UUID | None] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)


class ErrorLog(Base, TimestampMixin):
    """System error log."""

    __tablename__ = "error_log"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid7)
    session_id: Mapped[UUID | None] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=True
    )
    logger_name: Mapped[str] = mapped_column(String(100), nullable=False)
    level: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    traceback: Mapped[str | None] = mapped_column(Text, nullable=True)


class EmbeddingCache(Base, TimestampMixin):
    """Cache of content hash to embedding vector."""

    __tablename__ = "embedding_cache"

    content_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    model_name: Mapped[str] = mapped_column(String(100), primary_key=True)
    vector_data: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False)
