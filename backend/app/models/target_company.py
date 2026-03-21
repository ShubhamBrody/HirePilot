"""
Target Company Model

Stores companies a user is targeting for career page job scraping.
Each company can have its own scrape schedule and career page URL.
"""

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class URLDiscoveryMethod(str, enum.Enum):
    AI_DISCOVERED = "ai_discovered"
    USER_PROVIDED = "user_provided"
    VERIFIED = "verified"


class ScrapeStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    NEVER = "never"


class TargetCompany(Base):
    __tablename__ = "target_companies"
    __table_args__ = (
        UniqueConstraint("user_id", "company_name", name="uq_user_company"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Company details
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    career_page_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    url_discovery_method: Mapped[URLDiscoveryMethod | None] = mapped_column(
        Enum(URLDiscoveryMethod), nullable=True
    )
    url_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Scheduling
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    scrape_frequency_hours: Mapped[int] = mapped_column(
        Integer, default=12, nullable=False
    )

    # Scrape status tracking
    last_scraped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_scrape_status: Mapped[ScrapeStatus] = mapped_column(
        Enum(ScrapeStatus), default=ScrapeStatus.NEVER, nullable=False
    )
    last_scrape_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    jobs_found_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Scraping intelligence — cached selectors/strategies that worked
    scrape_strategy: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    scraping_logs = relationship(
        "CompanyScrapingLog",
        back_populates="target_company",
        lazy="noload",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<TargetCompany {self.company_name} (user={self.user_id})>"
