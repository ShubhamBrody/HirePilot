"""
Job Listing Model

Stores discovered job listings from all sources with AI match scores.
"""

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class JobSource(str, enum.Enum):
    LINKEDIN = "linkedin"
    INDEED = "indeed"
    NAUKRI = "naukri"
    COMPANY_CAREER = "company_career"
    OTHER = "other"


class JobListing(Base):
    __tablename__ = "job_listings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Foreign key to the user who discovered/tracks this job
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )

    # Job details
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remote_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # remote, hybrid, onsite
    description: Mapped[str] = mapped_column(Text, nullable=False)
    requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Source & tracking
    source: Mapped[JobSource] = mapped_column(
        Enum(JobSource), nullable=False, index=True
    )
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    source_job_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_logo_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Classification
    role_level: Mapped[str | None] = mapped_column(String(50), nullable=True)  # SDE1, SDE2, Senior, etc.
    technologies: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    company_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # startup, FAANG, etc.

    # AI Analysis
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    match_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_keywords: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array

    # Salary breakdown from LLM analysis
    estimated_salary_breakdown: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON

    # Metadata
    posted_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    # Soft-delete
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None, index=True
    )

    # Relationships
    recruiters = relationship("Recruiter", back_populates="job_listing", lazy="selectin")
    applications = relationship("Application", back_populates="job_listing", lazy="selectin", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<JobListing {self.title} @ {self.company}>"
