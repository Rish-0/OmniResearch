"""Decisions, Failures, Memory Ledger, Agent Execution, and LLM call telemetry models."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Float,
    ForeignKey,
    Index,
    Integer,
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


class Decision(Base, TimestampMixin):
    """Planner decision audit entry."""

    __tablename__ = "decisions"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid7)
    session_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    decision_type: Mapped[str] = mapped_column(String(100), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False, default=dict)


class Failure(Base, TimestampMixin):
    """Recorded failure for loop prevention and replan triage."""

    __tablename__ = "failures"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid7)
    session_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[str] = mapped_column(String(100), nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    failure_class: Mapped[str] = mapped_column(String(50), nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    error_signature: Mapped[str] = mapped_column(Text, nullable=False)
    traceback: Mapped[str] = mapped_column(Text, nullable=False, default="")
    spec_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        Index("idx_failures_session_fingerprint", "session_id", "fingerprint"),
    )


class MemoryEventModel(Base, TimestampMixin):
    """Episodic memory ledger entry (T2 memory tier)."""

    __tablename__ = "memory_events"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid7)
    session_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    agent: Mapped[str] = mapped_column(String(100), nullable=False)
    task_id: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    content: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False, default=dict)


class AgentRun(Base, TimestampMixin):
    """Agent execution tracking."""

    __tablename__ = "agent_runs"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid7)
    session_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[str] = mapped_column(String(100), nullable=False)
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="RUNNING")
    steps_taken: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


class AgentToolCall(Base, TimestampMixin):
    """Individual tool call log for agent step audit."""

    __tablename__ = "agent_tool_calls"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid7)
    agent_run_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    input_args: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False, default=dict)
    output_result: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False, default=dict)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_error: Mapped[bool] = mapped_column(default=False, nullable=False)


class LLMCall(Base, TimestampMixin):
    """Telemetry log for individual LLM requests."""

    __tablename__ = "llm_calls"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid7)
    session_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
