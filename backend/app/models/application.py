"""
Application Model

Tracks job applications with status pipeline and linked resume versions.
"""

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ApplicationStatus(str, enum.Enum):
    DRAFT = "draft"
    APPLYING = "applying"
    APPLIED = "applied"
    VIEWED = "viewed"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class ApplicationMethod(str, enum.Enum):
    MANUAL = "manual"
    AUTOMATED = "automated"
    REFERRAL = "referral"


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    job_listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_listings.id"), nullable=False
    )
    resume_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resume_versions.id"), nullable=False
    )

    # Application details
    company: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(500), nullable=False)
    job_description_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_letter: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Status tracking
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus), default=ApplicationStatus.DRAFT, index=True
    )
    method: Mapped[ApplicationMethod] = mapped_column(
        Enum(ApplicationMethod), default=ApplicationMethod.MANUAL
    )

    # Automation metadata
    automation_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    automation_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    form_data_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON

    # Dates
    applied_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    response_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    interview_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    user = relationship("User", back_populates="applications")
    job_listing = relationship("JobListing", back_populates="applications")
    resume_version = relationship("ResumeVersion", back_populates="applications")

    def __repr__(self) -> str:
        return f"<Application {self.role} @ {self.company} [{self.status.value}]>"
