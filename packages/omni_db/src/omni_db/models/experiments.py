"""Experiment design, execution runs, numeric results, and artifact models."""

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


class Experiment(Base, TimestampMixin):
    """Experiment specification and design."""

    __tablename__ = "experiments"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid7)
    session_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[str] = mapped_column(String(100), nullable=False)
    spec: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False)
    spec_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    __table_args__ = (
        Index("idx_experiments_session_hash", "session_id", "spec_hash"),
    )


class ExperimentRun(Base, TimestampMixin):
    """Execution run for a model + seed within an experiment."""

    __tablename__ = "experiment_runs"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid7)
    experiment_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    dataset_version_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("dataset_versions.id", ondelete="RESTRICT"), nullable=False
    )
    code_sha256: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    image_digest: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    mlflow_run_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    logs_s3_path: Mapped[str | None] = mapped_column(Text, nullable=True)


class Result(Base, TimestampMixin):
    """Evaluated numeric metric result from an experiment run."""

    __tablename__ = "results"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid7)
    run_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("experiment_runs.id", ondelete="CASCADE"), nullable=False
    )
    metric: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    split: Mapped[str] = mapped_column(String(50), nullable=False, default="validation")

    __table_args__ = (
        Index("idx_results_run_metric", "run_id", "metric"),
    )


class Artifact(Base, TimestampMixin):
    """File artifact produced by an experiment run or session."""

    __tablename__ = "artifacts"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid7)
    session_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[UUID | None] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("experiment_runs.id", ondelete="SET NULL"), nullable=True
    )
    artifact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    s3_path: Mapped[str] = mapped_column(Text, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
