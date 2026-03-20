"""
Subscription Model

Tracks user subscription plan, billing cycle, and feature limits.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    plan: Mapped[str] = mapped_column(
        String(50), nullable=False, default="free"
    )  # free, pro, enterprise
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="active"
    )  # active, cancelled, past_due
    price_monthly: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    billing_cycle: Mapped[str] = mapped_column(
        String(20), nullable=False, default="monthly"
    )  # monthly, yearly

    # Feature limits
    max_resumes: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    max_applications_per_day: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    max_job_scrapes_per_day: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    ai_tailoring_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    recruiter_outreach_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    autonomous_mode_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Mock billing
    mock_card_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    mock_next_billing_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


# Plan definitions
PLAN_CONFIGS = {
    "free": {
        "price_monthly": 0.0,
        "max_resumes": 3,
        "max_applications_per_day": 5,
        "max_job_scrapes_per_day": 10,
        "ai_tailoring_enabled": False,
        "recruiter_outreach_enabled": False,
        "autonomous_mode_enabled": False,
    },
    "pro": {
        "price_monthly": 9.99,
        "max_resumes": 25,
        "max_applications_per_day": 50,
        "max_job_scrapes_per_day": 100,
        "ai_tailoring_enabled": True,
        "recruiter_outreach_enabled": True,
        "autonomous_mode_enabled": False,
    },
    "enterprise": {
        "price_monthly": 29.99,
        "max_resumes": -1,  # unlimited
        "max_applications_per_day": -1,
        "max_job_scrapes_per_day": -1,
        "ai_tailoring_enabled": True,
        "recruiter_outreach_enabled": True,
        "autonomous_mode_enabled": True,
    },
}
