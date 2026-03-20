"""
Work Experience Schemas — CRUD request/response models.
"""

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator


class WorkExperienceCreate(BaseModel):
    company: str = Field(min_length=1, max_length=255)
    role: str = Field(min_length=1, max_length=255)
    location: str | None = None
    description: str | None = None
    start_date: str | None = None  # YYYY-MM-DD
    end_date: str | None = None  # YYYY-MM-DD (null if is_current)
    is_current: bool = False
    sort_order: int = 0


class WorkExperienceUpdate(BaseModel):
    company: str | None = None
    role: str | None = None
    location: str | None = None
    description: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool | None = None
    sort_order: int | None = None


class WorkExperienceResponse(BaseModel):
    id: str
    company: str
    role: str
    location: str | None = None
    description: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("id", mode="before")
    @classmethod
    def coerce_uuid(cls, v: object) -> str:
        return str(v) if v is not None else None

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def coerce_date(cls, v: object) -> str | None:
        if isinstance(v, date):
            return v.isoformat()
        return str(v) if v is not None else None


class WorkExperienceListResponse(BaseModel):
    experiences: list[WorkExperienceResponse]
    total: int
