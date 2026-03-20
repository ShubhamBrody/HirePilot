"""
Application Schemas — CRUD, status updates, filtering, analytics.
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

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
    resume_version_id: str | None = None
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

    @field_validator("id", "user_id", "job_listing_id", "resume_version_id", mode="before")
    @classmethod
    def coerce_uuid_to_str(cls, v: object) -> str | None:
        if v is None:
            return None
        return str(v)


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


# ── Apply Wizard Schemas ─────────────────────────────────────────


class WizardStartRequest(BaseModel):
    """Start the guided apply wizard for a job."""
    job_listing_id: str


class WizardStartResponse(BaseModel):
    """System describes what it's about to do; user must approve."""
    wizard_id: str
    job_title: str
    company: str
    job_description: str | None = None
    message: str  # "I'm about to tailor your resume for ..."
    step: str = "confirm_tailor"


class WizardTailorRequest(BaseModel):
    """User approves resume tailoring."""
    wizard_id: str
    base_resume_id: str | None = None  # use master if omitted


class WizardTailorResponse(BaseModel):
    """Returns the tailored resume for user review."""
    wizard_id: str
    tailored_latex: str
    changes_summary: str | None = None
    sections_modified: list[str] = []
    keywords_added: list[str] = []
    compile_success: bool = True
    message: str  # "Here's your tailored resume. Review it and..."
    step: str = "review_resume"


class WizardChatRequest(BaseModel):
    """User asks for modifications to the tailored resume."""
    wizard_id: str
    message: str
    current_latex: str
    history: list[dict[str, str]] = []


class WizardChatResponse(BaseModel):
    """AI returns updated resume based on user's chat message."""
    wizard_id: str
    updated_latex: str | None = None
    explanation: str
    compile_success: bool = True
    step: str = "review_resume"


class WizardApproveRequest(BaseModel):
    """User approves the final resume and wants to apply."""
    wizard_id: str
    job_listing_id: str
    final_latex: str
    resume_name: str | None = None


class WizardApproveResponse(BaseModel):
    """Resume saved, application created, ready to apply."""
    wizard_id: str
    application_id: str
    resume_version_id: str
    message: str  # "Resume saved and mapped. I'm about to apply via..."
    step: str = "confirm_apply"


class WizardAutoApplyRequest(BaseModel):
    """User approves the automated application."""
    application_id: str


class WizardAutoApplyResponse(BaseModel):
    """Auto-apply task has been queued."""
    application_id: str
    task_id: str
    message: str
    step: str = "applying"


class WizardStatusResponse(BaseModel):
    """Check the status of an in-progress application."""
    application_id: str
    status: str
    action_log: list[dict[str, str]] = []
    error: str | None = None
    step: str = "done"
