"""
Application Schemas — CRUD, status updates, filtering, analytics.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.application import ApplicationMethod, ApplicationStatus


class ApplicationCreateRequest(BaseModel):
    job_listing_id: str
    resume_version_id: str
    cover_letter: str | None = None
    notes: str | None = None
    method: ApplicationMethod = ApplicationMethod.MANUAL


class ApplicationUpdateRequest(BaseModel):
    cover_letter: str | None = None
    notes: str | None = None


class ApplicationStatusUpdateRequest(BaseModel):
    status: ApplicationStatus
    notes: str | None = None


class ApplicationResponse(BaseModel):
    id: str
    user_id: str
    job_listing_id: str
    resume_version_id: str
    company: str
    role: str
    job_description_snapshot: str | None = None
    cover_letter: str | None = None
    status: ApplicationStatus
    method: ApplicationMethod
    applied_date: datetime | None = None
    response_date: datetime | None = None
    interview_date: datetime | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApplicationListResponse(BaseModel):
    applications: list[ApplicationResponse]
    total: int
    page: int
    page_size: int


class ApplicationFilters(BaseModel):
    company: str | None = None
    role: str | None = None
    status: ApplicationStatus | None = None
    resume_version_id: str | None = None
    technology_focus: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class AutoApplyRequest(BaseModel):
    """Trigger automated job application."""
    job_listing_id: str
    resume_version_id: str
    cover_letter: str | None = None
    additional_form_data: dict[str, str] | None = None


class ApplicationAnalytics(BaseModel):
    total_applications: int
    by_status: dict[str, int]
    by_company: dict[str, int]
    by_method: dict[str, int]
    weekly_trend: list[dict[str, int | str]]
    response_rate: float
    interview_rate: float
