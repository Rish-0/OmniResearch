"""Dataset discovery and version management models."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
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


class Dataset(Base, TimestampMixin):
    """Dataset entity."""

    __tablename__ = "datasets"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid7)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    license: Mapped[str | None] = mapped_column(String(100), nullable=True)


class DatasetVersion(Base, TimestampMixin):
    """Immutable dataset version hash."""

    __tablename__ = "dataset_versions"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid7)
    dataset_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    size_samples: Mapped[int] = mapped_column(Integer, nullable=False)
    splits: Mapped[list[str]] = mapped_column(JSON_TYPE, nullable=False, default=list)
    leakage_checked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    staging_path: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        Index("idx_dataset_versions_dataset_hash", "dataset_id", "version_hash", unique=True),
    )


class ProjectDataset(Base, TimestampMixin):
    """Link dataset to project."""

    __tablename__ = "project_datasets"

    project_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    dataset_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), primary_key=True
    )
    task_fit_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
