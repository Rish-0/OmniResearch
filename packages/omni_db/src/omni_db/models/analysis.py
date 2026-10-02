"""Analysis, Claims, Evidence, Verification, and Report models."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
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


class Analysis(Base, TimestampMixin):
    """Analysis facts emitted by the Analysis Agent."""

    __tablename__ = "analyses"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid7)
    session_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[str] = mapped_column(String(100), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    numeric_bindings: Mapped[list[dict[str, Any]]] = mapped_column(JSON_TYPE, nullable=False, default=list)
    statistical_tests: Mapped[list[dict[str, Any]]] = mapped_column(JSON_TYPE, nullable=False, default=list)
    comparison_notes: Mapped[list[str]] = mapped_column(JSON_TYPE, nullable=False, default=list)


class Claim(Base, TimestampMixin):
    """Research claim asserted from analysis."""

    __tablename__ = "claims"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid7)
    session_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    numeric_bindings: Mapped[list[dict[str, Any]]] = mapped_column(JSON_TYPE, nullable=False, default=list)
    section: Mapped[str] = mapped_column(String(100), nullable=False, default="")

    __table_args__ = (
        Index("idx_claims_session_status", "session_id", "status"),
        CheckConstraint(
            "status IN ('PENDING', 'VERIFIED', 'FAILED', 'WEAKENED', 'DROPPED')",
            name="check_claim_status",
        ),
    )


class ClaimEvidence(Base, TimestampMixin):
    """Mapping between claim and supporting/contradicting evidence."""

    __tablename__ = "claim_evidence"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid7)
    claim_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE"), nullable=False
    )
    evidence_type: Mapped[str] = mapped_column(String(50), nullable=False)  # result, citation, stat_test
    result_id: Mapped[UUID | None] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("results.id", ondelete="SET NULL"), nullable=True
    )
    paper_asset_id: Mapped[UUID | None] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("paper_assets.id", ondelete="SET NULL"), nullable=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    relationship: Mapped[str] = mapped_column(String(50), nullable=False, default="supports")

    __table_args__ = (
        Index("idx_claim_evidence_claim_id", "claim_id"),
    )


class Citation(Base, TimestampMixin):
    """Citation resolving claim/report text to source paper asset."""

    __tablename__ = "citations"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid7)
    claim_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True
    )
    paper_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("papers.id", ondelete="RESTRICT"), nullable=False
    )
    paper_asset_id: Mapped[UUID | None] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("paper_assets.id", ondelete="SET NULL"), nullable=True
    )
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bbox: Mapped[list[float] | None] = mapped_column(JSON_TYPE, nullable=True)
    quote: Mapped[str | None] = mapped_column(Text, nullable=True)


class Verification(Base, TimestampMixin):
    """Aggregate verification check output."""

    __tablename__ = "verifications"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid7)
    session_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    overall_pass: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")


class VerificationFinding(Base, TimestampMixin):
    """Individual V1-V7 verification finding."""

    __tablename__ = "verification_findings"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid7)
    verification_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("verifications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    check_type: Mapped[str] = mapped_column(String(10), nullable=False)  # V1..V7
    target_id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), nullable=False)
    verdict: Mapped[str] = mapped_column(String(50), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False)
    is_blocking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint(
            "verdict IN ('SUPPORTED', 'PARTIAL', 'UNSUPPORTED', 'CONTRADICTED', 'ABSTAIN')",
            name="check_verification_verdict",
        ),
    )


class Report(Base, TimestampMixin):
    """Final research report."""

    __tablename__ = "reports"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid7)
    session_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_partial: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    s3_path: Mapped[str | None] = mapped_column(Text, nullable=True)


class ReportSection(Base, TimestampMixin):
    """Report section item."""

    __tablename__ = "report_sections"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid7)
    report_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_name: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    ordering: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
