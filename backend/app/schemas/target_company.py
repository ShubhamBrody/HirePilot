"""
Target Company Schemas — Request/response models for company career search.
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.target_company import ScrapeStatus, URLDiscoveryMethod


# ── Request Models ───────────────────────────────────────────────


class TargetCompanyCreate(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=255)
    career_page_url: str | None = Field(None, max_length=1000)
    scrape_frequency_hours: int = Field(12, ge=6, le=168)


class TargetCompanyUpdate(BaseModel):
    career_page_url: str | None = None
    is_enabled: bool | None = None
    scrape_frequency_hours: int | None = Field(None, ge=6, le=168)


class BulkCompanyCreate(BaseModel):
    """Add multiple companies at once."""
    company_names: list[str] = Field(..., min_length=1, max_length=50)
    scrape_frequency_hours: int = Field(12, ge=6, le=168)


# ── Response Models ──────────────────────────────────────────────


class TargetCompanyResponse(BaseModel):
    id: str
    company_name: str
    career_page_url: str | None = None
    url_discovery_method: URLDiscoveryMethod | None = None
    url_verified: bool
    is_enabled: bool
    scrape_frequency_hours: int
    last_scraped_at: datetime | None = None
    last_scrape_status: ScrapeStatus
    last_scrape_error: str | None = None
    jobs_found_total: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id_to_str(cls, v: object) -> str:
        return str(v)


class TargetCompanyListResponse(BaseModel):
    companies: list[TargetCompanyResponse]
    total: int


class ScrapingLogResponse(BaseModel):
    id: str
    target_company_id: str
    started_at: datetime
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    status: str
    jobs_found: int
    new_jobs_saved: int
    error_message: str | None = None
    error_type: str | None = None
    page_url_used: str | None = None
    retry_count: int
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("id", "target_company_id", mode="before")
    @classmethod
    def coerce_ids_to_str(cls, v: object) -> str:
        return str(v)


class ScrapingLogListResponse(BaseModel):
    logs: list[ScrapingLogResponse]
    total: int


class DiscoverURLResponse(BaseModel):
    career_url: str | None = None
    confidence: float = 0.0
    alternate_urls: list[str] = []
    error: str | None = None


class ScrapeCompanyResponse(BaseModel):
    """Response when triggering a manual scrape."""
    message: str
    task_id: str | None = None


class CompanySearchSettingsUpdate(BaseModel):
    """Update user's company search preferences."""
    company_search_enabled: bool | None = None
    linkedin_search_enabled: bool | None = None
    auto_apply_threshold: float | None = Field(None, ge=0.0, le=1.0)
