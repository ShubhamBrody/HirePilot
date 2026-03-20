"""
Onboarding Schemas — Multi-step wizard request/response models.

8 steps:
1. Personal Info
2. Work Experience
3. Salary & Compensation
4. Skills (with LLM classification)
5. Job Preferences
6. Platform Credentials
7. Resume Upload
8. Education & EEO
"""

from pydantic import BaseModel, EmailStr, Field


# ── Step 1: Personal Info ────────────────────────────────────────


class OnboardingStep1Request(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    email_for_outreach: EmailStr | None = None
    phone: str | None = None
    date_of_birth: str | None = None  # ISO format: YYYY-MM-DD
    gender: str | None = Field(None, pattern="^(male|female|non_binary|prefer_not_to_say)$")
    nationality: str | None = None
    address: dict | None = None  # {street, city, state, zip, country}
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None


# ── Step 2: Work Experience ──────────────────────────────────────


class OnboardingStep2Request(BaseModel):
    current_company: str | None = None
    current_title: str | None = None
    years_of_experience: int | None = Field(None, ge=0, le=50)
    headline: str | None = Field(None, max_length=500)
    summary: str | None = None
    experience_level: str | None = Field(None, pattern="^(intern|junior|mid|senior|staff|lead|principal)$")
    notice_period_days: int | None = Field(None, ge=0, le=365)
    work_authorization: str | None = Field(
        None,
        pattern="^(citizen|permanent_resident|h1b|l1|opt|ead|need_sponsorship|other)$",
    )


# ── Step 3: Salary & Compensation ───────────────────────────────


class OnboardingStep3Request(BaseModel):
    current_salary_base: float | None = Field(None, ge=0)
    current_salary_bonus: float | None = Field(None, ge=0)
    current_salary_rsu: float | None = Field(None, ge=0)
    salary_currency: str = Field("USD", max_length=10)
    expected_salary_min: float | None = Field(None, ge=0)
    expected_salary_max: float | None = Field(None, ge=0)


# ── Step 4: Skills ───────────────────────────────────────────────


class OnboardingStep4Request(BaseModel):
    raw_skills: list[str] = Field(default_factory=list)
    classified_skills: dict[str, list[str]] | None = None  # Override after classification


class SkillClassificationRequest(BaseModel):
    skills: list[str] = Field(min_length=1)


class SkillClassificationResponse(BaseModel):
    classified: dict[str, list[str]]
    categories: list[str] = [
        "Languages",
        "Frameworks",
        "Databases",
        "Cloud & DevOps",
        "Tools",
        "Architecture & Patterns",
        "Soft Skills",
        "Other",
    ]


# ── Step 5: Job Preferences ─────────────────────────────────────


class OnboardingStep5Request(BaseModel):
    target_roles: list[str] | None = None
    preferred_technologies: list[str] | None = None
    preferred_companies: list[str] | None = None
    preferred_location: str | None = None
    job_search_keywords: str | None = None
    willing_to_relocate: bool | None = None
    remote_preference: str | None = Field(None, pattern="^(remote|hybrid|onsite|any)$")
    job_type_preference: str | None = Field(None, pattern="^(full_time|contract|either)$")


# ── Step 6: Platform Credentials ────────────────────────────────


class PlatformCredentialItem(BaseModel):
    platform: str = Field(pattern="^(linkedin|indeed|naukri)$")
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=255)


class OnboardingStep6Request(BaseModel):
    credentials: list[PlatformCredentialItem] = Field(default_factory=list)


# ── Step 7: Resume Upload ───────────────────────────────────────


class OnboardingStep7Request(BaseModel):
    latex_source: str | None = None  # Direct LaTeX paste
    # PDF upload handled separately via multipart endpoint


class ResumeUploadResponse(BaseModel):
    latex_source: str
    method: str  # "direct_latex" or "pdf_converted"
    compilation_status: str = "pending"


# ── Step 8: Education & EEO ─────────────────────────────────────


class EducationEntry(BaseModel):
    degree: str
    field: str | None = None
    institution: str
    year: int | None = None
    gpa: str | None = None


class OnboardingStep8Request(BaseModel):
    education: list[EducationEntry] = Field(default_factory=list)
    disability_status: str | None = Field(
        None, pattern="^(yes|no|prefer_not_to_say)$"
    )
    veteran_status: str | None = Field(
        None, pattern="^(yes|no|prefer_not_to_say|protected)$"
    )
    cover_letter_default: str | None = None


# ── Progress & Summary ───────────────────────────────────────────


class OnboardingProgressResponse(BaseModel):
    current_step: int
    total_steps: int = 8
    completed: bool
    steps_status: dict[str, bool]  # {"1": True, "2": True, "3": False, ...}


class OnboardingSummaryResponse(BaseModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    headline: str | None = None
    current_company: str | None = None
    current_title: str | None = None
    years_of_experience: int | None = None
    experience_level: str | None = None
    salary_currency: str | None = None
    current_salary_ctc: float | None = None
    expected_salary_min: float | None = None
    expected_salary_max: float | None = None
    classified_skills: dict[str, list[str]] | None = None
    target_roles: list[str] | None = None
    preferred_location: str | None = None
    remote_preference: str | None = None
    has_linkedin_creds: bool = False
    has_indeed_creds: bool = False
    has_naukri_creds: bool = False
    has_resume: bool = False
    education_count: int = 0
    onboarding_completed: bool = False
