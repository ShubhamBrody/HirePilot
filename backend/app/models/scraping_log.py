"""
Company Scraping Log Model

Tracks every scrape attempt for a target company with error classification
to support adaptive scraping intelligence.
"""

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ScrapingRunStatus(str, enum.Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


class ScrapingErrorType(str, enum.Enum):
    TIMEOUT = "timeout"
    BLOCKED = "blocked"
    STRUCTURE_CHANGE = "structure_change"
    NETWORK = "network"
    CAPTCHA = "captcha"
    AUTH_REQUIRED = "auth_required"
    OTHER = "other"


class CompanyScrapingLog(Base):
    __tablename__ = "company_scraping_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    target_company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("target_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )

    # Timing
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Results
    status: Mapped[ScrapingRunStatus] = mapped_column(
        Enum(ScrapingRunStatus), default=ScrapingRunStatus.RUNNING, nullable=False
    )
    jobs_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    new_jobs_saved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_type: Mapped[ScrapingErrorType | None] = mapped_column(
        Enum(ScrapingErrorType), nullable=True
    )

    # Snapshot of URL used for this scrape
    page_url_used: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Strategy metadata — what approach was used for this scrape
    strategy_used: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    # Relationships
    target_company = relationship("TargetCompany", back_populates="scraping_logs")

    def __repr__(self) -> str:
        return f"<CompanyScrapingLog {self.target_company_id} [{self.status.value}]>"
