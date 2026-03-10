"""
Resume Schemas — Resume version CRUD, tailoring requests, compilation.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class ResumeVersionCreateRequest(BaseModel):
    name: str = Field(max_length=255)
    description: str | None = None
    latex_source: str
    template_id: str | None = None
    target_company: str | None = None
    target_role: str | None = None
    focus_area: str | None = None
    technologies: list[str] | None = None
    is_master: bool = False


class ResumeVersionUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    latex_source: str | None = None
    target_company: str | None = None
    target_role: str | None = None
    focus_area: str | None = None
    technologies: list[str] | None = None


class ResumeVersionResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    version_number: int
    latex_source: str
    template_id: str | None = None
    pdf_s3_key: str | None = None
    compilation_status: str
    compilation_errors: str | None = None
    target_company: str | None = None
    target_role: str | None = None
    focus_area: str | None = None
    technologies: str | None = None
    ai_tailored: bool
    ai_changes_summary: str | None = None
    is_master: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ResumeListResponse(BaseModel):
    resumes: list[ResumeVersionResponse]
    total: int


class ResumeTailorRequest(BaseModel):
    """Request to AI-tailor a resume for a specific job."""
    job_listing_id: str
    base_resume_id: str | None = Field(
        None, description="Resume to use as base. Defaults to master resume."
    )
    focus_skills: list[str] | None = None
    additional_instructions: str | None = None


class ResumeTailorResponse(BaseModel):
    resume_version_id: str
    name: str
    changes_summary: str
    matched_keywords: list[str]
    optimization_score: float


class ResumeCompileRequest(BaseModel):
    latex_source: str | None = Field(
        None, description="Override LaTeX source. If None, uses stored source."
    )


class ResumeCompileResponse(BaseModel):
    resume_version_id: str
    status: str  # compiling, success, error
    pdf_url: str | None = None
    errors: list[str] | None = None


class ResumeTemplateResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    category: str
    preview_image_url: str | None = None

    model_config = {"from_attributes": True}
