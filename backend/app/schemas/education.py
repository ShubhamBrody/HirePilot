"""
Education Schemas — CRUD request/response models with degree/field choices.
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.education import DEGREE_CHOICES, FIELD_OF_STUDY_CHOICES


class EducationCreate(BaseModel):
    degree: str = Field(min_length=1, max_length=100)
    custom_degree: str | None = None  # When degree == "Other"
    field_of_study: str | None = None
    custom_field: str | None = None  # When field_of_study == "Other"
    institution: str = Field(min_length=1, max_length=255)
    start_year: int | None = Field(None, ge=1950, le=2040)
    end_year: int | None = Field(None, ge=1950, le=2040)
    gpa: float | None = Field(None, ge=0, le=10)
    gpa_scale: float | None = Field(None, ge=1, le=10)
    activities: str | None = None
    sort_order: int = 0


class EducationUpdate(BaseModel):
    degree: str | None = None
    custom_degree: str | None = None
    field_of_study: str | None = None
    custom_field: str | None = None
    institution: str | None = None
    start_year: int | None = None
    end_year: int | None = None
    gpa: float | None = None
    gpa_scale: float | None = None
    activities: str | None = None
    sort_order: int | None = None


class EducationResponse(BaseModel):
    id: str
    degree: str
    custom_degree: str | None = None
    field_of_study: str | None = None
    custom_field: str | None = None
    institution: str
    start_year: int | None = None
    end_year: int | None = None
    gpa: float | None = None
    gpa_scale: float | None = None
    activities: str | None = None
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("id", mode="before")
    @classmethod
    def coerce_uuid(cls, v: object) -> str:
        return str(v) if v is not None else None


class EducationListResponse(BaseModel):
    educations: list[EducationResponse]
    total: int


class EducationChoicesResponse(BaseModel):
    degree_choices: list[str] = DEGREE_CHOICES
    field_of_study_choices: list[str] = FIELD_OF_STUDY_CHOICES
