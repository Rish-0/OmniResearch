"""Research Session, Plan Version, Task, and Task Attempt models."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
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
from omni_db.models.base import Base, OrgMixin, TimestampMixin

# Use JSONB for Postgres, falling back to JSON for non-postgres if needed
JSON_TYPE = JSONB().with_variant(JSON(), "sqlite")


class ResearchSession(Base, OrgMixin, TimestampMixin):
    """Research session lifecycle state and aggregate budget tracking."""

    __tablename__ = "research_sessions"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid7)
    project_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="INIT")
    budgets: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False, default=dict)
    usage: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False, default=dict)
    replan_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checkpoint_thread_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lease_worker_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lease_expires_at: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('INIT', 'PLAN', 'RESEARCH', 'DATASET', 'EXPERIMENT', "
            "'ANALYSIS', 'VERIFY', 'REPORT', 'COMPLETE', 'PAUSED', "
            "'NEEDS_HUMAN', 'FAILED', 'CANCELLED')",
            name="check_session_status",
        ),
        Index("idx_research_sessions_org_project", "org_id", "project_id"),
    )


class PlanVersion(Base, TimestampMixin):
    """Versioned plan DAG snapshot."""

    __tablename__ = "plan_versions"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid7)
    session_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    plan_data: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False)

    __table_args__ = (
        Index("idx_plan_versions_session_version", "session_id", "version", unique=True),
    )


class Task(Base, TimestampMixin):
    """A task instance within a research session plan."""

    __tablename__ = "tasks"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid7)
    session_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[str] = mapped_column(String(100), nullable=False)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    depends_on: Mapped[list[str]] = mapped_column(JSON_TYPE, nullable=False, default=list)
    acceptance_criteria: Mapped[list[str]] = mapped_column(JSON_TYPE, nullable=False, default=list)
    retry_budget: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    __table_args__ = (
        Index("idx_tasks_session_status", "session_id", "status"),
        Index("idx_tasks_session_task_id", "session_id", "task_id", unique=True),
        CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'SKIPPED', 'CANCELLED')",
            name="check_task_status",
        ),
    )


class TaskAttempt(Base, TimestampMixin):
    """Execution attempt of a task."""

    __tablename__ = "task_attempts"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid7)
    task_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    outputs: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False, default=dict)
    fingerprint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_task_attempts_task_attempt", "task_id", "attempt_no", unique=True),
    )
