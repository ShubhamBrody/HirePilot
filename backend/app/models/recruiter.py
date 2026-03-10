"""
Recruiter & Outreach Message Models

Stores recruiter profiles and tracks all outreach communications.
"""

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ConnectionStatus(str, enum.Enum):
    NOT_CONNECTED = "not_connected"
    PENDING = "pending"
    CONNECTED = "connected"
    BLOCKED = "blocked"


class OutreachStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    REPLIED = "replied"
    FAILED = "failed"


class Recruiter(Base):
    __tablename__ = "recruiters"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    job_listing_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_listings.id"), nullable=True
    )

    # Recruiter details
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True, unique=True)
    profile_image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Connection tracking
    connection_status: Mapped[ConnectionStatus] = mapped_column(
        Enum(ConnectionStatus), default=ConnectionStatus.NOT_CONNECTED
    )
    platform: Mapped[str] = mapped_column(String(50), default="linkedin")

    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    # Relationships
    job_listing = relationship("JobListing", back_populates="recruiters")
    messages = relationship("OutreachMessage", back_populates="recruiter", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Recruiter {self.name} @ {self.company}>"


class OutreachMessage(Base):
    __tablename__ = "outreach_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    recruiter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recruiters.id"), nullable=False
    )

    # Message content
    message_type: Mapped[str] = mapped_column(String(50), nullable=False)  # connection_request, follow_up, inmail
    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    ai_generated: Mapped[bool] = mapped_column(default=True)

    # Status tracking
    status: Mapped[OutreachStatus] = mapped_column(
        Enum(OutreachStatus), default=OutreachStatus.PENDING
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    # Relationships
    recruiter = relationship("Recruiter", back_populates="messages")

    def __repr__(self) -> str:
        return f"<OutreachMessage {self.message_type} -> {self.recruiter_id}>"
