"""
Education Model

Stores individual education entries for each user with structured degree types.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

# Predefined degree choices (frontend sends the key, display value for reference)
DEGREE_CHOICES = [
    "BTech",
    "BE",
    "BSc",
    "BA",
    "BCom",
    "BCA",
    "BBA",
    "MTech",
    "ME",
    "MSc",
    "MA",
    "MCom",
    "MCA",
    "MBA",
    "PhD",
    "MD",
    "JD",
    "BS",
    "MS",
    "AA",
    "AS",
    "Diploma",
    "Other",
]

FIELD_OF_STUDY_CHOICES = [
    "Computer Science",
    "Information Technology",
    "Software Engineering",
    "Electrical Engineering",
    "Electronics & Communication",
    "Mechanical Engineering",
    "Civil Engineering",
    "Data Science",
    "Artificial Intelligence",
    "Mathematics",
    "Physics",
    "Chemistry",
    "Biology",
    "Business Administration",
    "Finance",
    "Economics",
    "Commerce",
    "Psychology",
    "English",
    "Other",
]


class Education(Base):
    __tablename__ = "educations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    degree: Mapped[str] = mapped_column(String(100), nullable=False)  # From DEGREE_CHOICES or custom
    custom_degree: Mapped[str | None] = mapped_column(String(255), nullable=True)  # When degree == "Other"
    field_of_study: Mapped[str | None] = mapped_column(String(255), nullable=True)  # From FIELD_OF_STUDY_CHOICES
    custom_field: Mapped[str | None] = mapped_column(String(255), nullable=True)  # When field == "Other"
    institution: Mapped[str] = mapped_column(String(255), nullable=False)

    start_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gpa: Mapped[float | None] = mapped_column(Float, nullable=True)
    gpa_scale: Mapped[float | None] = mapped_column(Float, nullable=True, default=10.0)  # 4.0 or 10.0

    # Extra info
    activities: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Ordering
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    user = relationship("User", back_populates="educations")

    def __repr__(self) -> str:
        return f"<Education {self.degree} @ {self.institution}>"
