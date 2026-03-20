"""
Job Schemas — Search filters, job listing responses, match scoring.
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.job import JobSource


class JobSearchFilters(BaseModel):
    """Filters for job discovery."""
    role: str | None = Field(None, description="Target role e.g. 'SDE 2', 'Backend Engineer'")
    technologies: list[str] | None = Field(None, description="Tech stack filter: ['Java', 'Python']")
    location: str | None = None
    remote_type: str | None = Field(None, description="remote, hybrid, onsite")
    company_type: str | None = Field(None, description="startup, FAANG, enterprise")
    salary_min: int | None = None
    sources: list[JobSource] | None = None
    keywords: list[str] | None = None
    max_results: int = Field(50, ge=1, le=200)


class JobListingResponse(BaseModel):
    id: str
    title: str
    company: str
    location: str | None = None
    remote_type: str | None = None
    description: str
    requirements: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    source: JobSource
    source_url: str
    company_logo_url: str | None = None
    role_level: str | None = None
    technologies: str | None = None
    company_type: str | None = None
    match_score: float | None = None
    match_reasoning: str | None = None
    extracted_keywords: str | None = None
    posted_date: datetime | None = None
    is_active: bool
    discovered_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id_to_str(cls, v: object) -> str:
        return str(v)


class JobListingListResponse(BaseModel):
    jobs: list[JobListingResponse]
    total: int
    page: int
    page_size: int


class JobMatchScoreResponse(BaseModel):
    job_id: str
    match_score: float
    reasoning: str
    matched_skills: list[str]
    missing_skills: list[str]
    strengths: list[str] = []
    weaknesses: list[str] = []
    recommendations: list[str]


class TriggerJobSearchRequest(BaseModel):
    """Trigger an async job search with given filters."""
    filters: JobSearchFilters
    sources: list[JobSource] = [JobSource.LINKEDIN, JobSource.INDEED]


# ── Manual Job URL Scraping ──────────────────────────────────────


class ScrapeJobURLRequest(BaseModel):
    """User submits a job URL to scrape and analyze."""
    url: str
    resume_id: str | None = Field(None, description="Resume to compare against for fit scoring")


class ScrapeJobURLResponse(BaseModel):
    job: JobListingResponse | None = None
    fit_analysis: JobMatchScoreResponse | None = None
    error: str | None = None
