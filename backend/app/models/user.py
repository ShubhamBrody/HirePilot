"""
User Model

Stores user accounts with hashed passwords and encrypted platform credentials.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    headline: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # OAuth fields
    oauth_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)  # google, github
    oauth_provider_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    skills: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array stored as text
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    github_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    portfolio_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Encrypted platform credentials (LinkedIn, Indeed, etc.)
    encrypted_linkedin_creds: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_indeed_creds: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_naukri_creds: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Master resume (LaTeX source)
    master_resume_latex: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Job search preferences
    job_search_keywords: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferred_location: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Structured onboarding profile (Section 1 of design doc)
    target_roles: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array: ["SDE 2", "Backend Engineer"]
    preferred_technologies: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array: ["Python", "Java"]
    preferred_companies: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array: ["Google", "Stripe"]
    experience_level: Mapped[str | None] = mapped_column(String(50), nullable=True)  # junior, mid, senior, lead
    email_for_outreach: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Gmail integration (encrypted refresh token)
    gmail_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Company career search settings ───────────────────────────
    auto_apply_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0.0-1.0
    company_search_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    linkedin_search_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default="true")

    # ── Onboarding questionnaire fields ──────────────────────────

    # Personal information
    date_of_birth: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    nationality: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: {street, city, state, zip, country}

    # Work history
    current_company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    years_of_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notice_period_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    work_authorization: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Salary & compensation
    current_salary_base: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_salary_bonus: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_salary_rsu: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_salary_ctc: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(String(10), nullable=True, default="USD")
    expected_salary_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_salary_max: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Education (JSON array: [{degree, field, institution, year, gpa}])
    education: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Job preferences
    willing_to_relocate: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    remote_preference: Mapped[str | None] = mapped_column(String(50), nullable=True)  # remote, hybrid, onsite, any
    job_type_preference: Mapped[str | None] = mapped_column(String(50), nullable=True)  # full_time, contract, either

    # Classified skills (JSON: {languages: [], frameworks: [], databases: [], ...})
    classified_skills: Mapped[str | None] = mapped_column(Text, nullable=True)

    # EEO & misc
    cover_letter_default: Mapped[str | None] = mapped_column(Text, nullable=True)
    disability_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    veteran_status: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Onboarding tracking
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    onboarding_step: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default="0")

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    resume_versions = relationship("ResumeVersion", back_populates="user", lazy="selectin")
    applications = relationship("Application", back_populates="user", lazy="selectin")
    work_experiences = relationship("WorkExperience", back_populates="user", lazy="selectin", order_by="WorkExperience.sort_order")
    educations = relationship("Education", back_populates="user", lazy="selectin", order_by="Education.sort_order")
    audit_logs = relationship("AuditLog", back_populates="user", lazy="noload")
    target_companies = relationship("TargetCompany", lazy="noload", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User {self.email}>"
