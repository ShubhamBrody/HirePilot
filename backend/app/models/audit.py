"""
Audit Log Model

Records every automation action for security, debugging, and compliance.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    # Action details
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    module: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # scraper, outreach, automation, etc.
    entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True)   # job, recruiter, application, etc.
    entity_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Context
    details: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Result
    status: Mapped[str] = mapped_column(String(50), default="success")  # success, failure, warning
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )

    # Relationships
    user = relationship("User", back_populates="audit_logs")

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} by {self.user_id} [{self.status}]>"
