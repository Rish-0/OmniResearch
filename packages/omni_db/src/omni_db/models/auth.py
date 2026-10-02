"""User, Role, Project, and Member models."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import UUID as SQLUUID
from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from omni_core.ids import uuid7
from omni_db.models.base import Base, OrgMixin, TimestampMixin


class User(Base, TimestampMixin):
    """User entity."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid7)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)


class Role(Base):
    """RBAC Role definitions."""

    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(50), primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    __table_args__ = (
        CheckConstraint(
            "name IN ('viewer', 'researcher', 'project_admin', 'org_admin')",
            name="check_role_name",
        ),
    )


class Project(Base, OrgMixin, TimestampMixin):
    """Research Project."""

    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid7)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_archived: Mapped[bool] = mapped_column(default=False, nullable=False)


class ProjectMember(Base, TimestampMixin):
    """Project membership with RBAC role."""

    __tablename__ = "project_members"

    project_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(
        String(50), ForeignKey("roles.name", ondelete="RESTRICT"), nullable=False
    )
