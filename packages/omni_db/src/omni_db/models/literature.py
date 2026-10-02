"""Literature and paper ingestion models."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Float,
    ForeignKey,
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


class Paper(Base, TimestampMixin):
    """Academic paper entity."""

    __tablename__ = "papers"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid7)
    title: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    authors: Mapped[list[str]] = mapped_column(JSON_TYPE, nullable=False, default=list)
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True, index=True)
    arxiv_id: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True, index=True)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    pdf_s3_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False, default=dict)


class ProjectPaper(Base, TimestampMixin):
    """Linking paper to a project."""

    __tablename__ = "project_papers"

    project_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    paper_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True
    )
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    screening_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)


class IngestionJob(Base, TimestampMixin):
    """PDF ingestion pipeline job."""

    __tablename__ = "ingestion_jobs"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid7)
    paper_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    injection_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class PaperAsset(Base, TimestampMixin):
    """Paper asset (page image, figure crop, table JSON/CSV, equation)."""

    __tablename__ = "paper_assets"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid7)
    paper_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)  # figure, table, equation, page
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bbox: Mapped[list[float] | None] = mapped_column(JSON_TYPE, nullable=True)  # [x0, y0, x1, y1]
    content_json: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False, default=dict)
    s3_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)


class ReportedResult(Base, TimestampMixin):
    """Extracted numeric result reported in a paper."""

    __tablename__ = "reported_results"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid7)
    paper_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asset_id: Mapped[UUID | None] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("paper_assets.id", ondelete="SET NULL"), nullable=True
    )
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    dataset_name: Mapped[str] = mapped_column(String(255), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    reported_value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
