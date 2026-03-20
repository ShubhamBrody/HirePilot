"""
Resume Models

Stores resume versions (LaTeX source + compiled PDF metadata) and templates.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ResumeVersion(Base):
    __tablename__ = "resume_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    # Resume metadata
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1)

    # Content
    latex_source: Mapped[str] = mapped_column(Text, nullable=False)
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resume_templates.id"), nullable=True
    )

    # Compiled output
    pdf_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    pdf_file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    compilation_status: Mapped[str] = mapped_column(
        String(50), default="pending"
    )  # pending, compiling, success, error
    compilation_errors: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Targeting metadata
    target_company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_role: Mapped[str | None] = mapped_column(String(255), nullable=True)
    focus_area: Mapped[str | None] = mapped_column(String(255), nullable=True)
    technologies: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    tailored_for_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_listings.id"), nullable=True
    )

    # AI metadata
    ai_tailored: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_prompt_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_changes_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Parsed sections (JSON: {skills, experience, projects, achievements, education})
    parsed_sections: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_master: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Soft-delete
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None, index=True
    )

    # Relationships
    user = relationship("User", back_populates="resume_versions")
    template = relationship("ResumeTemplate", lazy="joined")
    applications = relationship("Application", back_populates="resume_version")

    def __repr__(self) -> str:
        return f"<ResumeVersion {self.name} v{self.version_number}>"


class ResumeTemplate(Base):
    __tablename__ = "resume_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(100), default="general")
    latex_source: Mapped[str] = mapped_column(Text, nullable=False)
    preview_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    def __repr__(self) -> str:
        return f"<ResumeTemplate {self.name}>"
