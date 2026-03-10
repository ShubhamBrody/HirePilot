"""
User Model

Stores user accounts with hashed passwords and encrypted platform credentials.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, String, Text
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
    audit_logs = relationship("AuditLog", back_populates="user", lazy="noload")

    def __repr__(self) -> str:
        return f"<User {self.email}>"
