"""
Onboarding Endpoints — Multi-step wizard API.

Collects user profile data for auto-filling job applications:
1. Personal Info
2. Work Experience
3. Salary & Compensation
4. Skills (with LLM classification)
5. Job Preferences
6. Platform Credentials
7. Resume Upload (PDF or LaTeX)
8. Education & EEO
"""

import io
import json
import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger
from app.core.security import encrypt_credential, get_current_user_id
from app.models.education import Education
from app.models.resume import ResumeVersion
from app.models.work_experience import WorkExperience
from app.repositories.education_repo import EducationRepository
from app.repositories.resume_repo import ResumeRepository
from app.repositories.user_repo import UserRepository
from app.repositories.work_experience_repo import WorkExperienceRepository
from app.schemas.onboarding import (
    OnboardingProgressResponse,
    OnboardingStep1Request,
    OnboardingStep2Request,
    OnboardingStep3Request,
    OnboardingStep4Request,
    OnboardingStep5Request,
    OnboardingStep6Request,
    OnboardingStep7Request,
    OnboardingStep8Request,
    OnboardingSummaryResponse,
    ResumeUploadResponse,
    SkillClassificationRequest,
    SkillClassificationResponse,
)
from app.services.llm_service import LLMService

router = APIRouter()
logger = get_logger(__name__)

TOTAL_STEPS = 8


# ── Progress ─────────────────────────────────────────────────────


@router.get("/progress", response_model=OnboardingProgressResponse)
async def get_onboarding_progress(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get current onboarding progress."""
    repo = UserRepository(db)
    user = await repo.get_by_id(uuid.UUID(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    step = user.onboarding_step or 0
    steps_status = {str(i): i <= step for i in range(1, TOTAL_STEPS + 1)}
    return OnboardingProgressResponse(
        current_step=step,
        total_steps=TOTAL_STEPS,
        completed=user.onboarding_completed,
        steps_status=steps_status,
    )


# ── Step Endpoints ───────────────────────────────────────────────


@router.post("/step/1")
async def save_step_1(
    data: OnboardingStep1Request,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Step 1: Personal Info."""
    repo = UserRepository(db)
    user = await repo.get_by_id(uuid.UUID(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    updates: dict = {
        "full_name": data.full_name,
        "phone": data.phone,
        "email_for_outreach": data.email_for_outreach,
        "linkedin_url": data.linkedin_url,
        "github_url": data.github_url,
        "portfolio_url": data.portfolio_url,
        "gender": data.gender,
        "nationality": data.nationality,
    }
    if data.date_of_birth:
        updates["date_of_birth"] = date.fromisoformat(data.date_of_birth)
    if data.address:
        updates["address"] = json.dumps(data.address)

    _advance_step(updates, user.onboarding_step, 1)
    await repo.update(user, updates)
    await db.commit()
    return {"message": "Step 1 saved", "step": 1}


@router.post("/step/2")
async def save_step_2(
    data: OnboardingStep2Request,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Step 2: Work Experience — accepts multiple entries with is_current flag."""
    repo = UserRepository(db)
    user = await repo.get_by_id(uuid.UUID(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Save structured work experiences to normalized table
    exp_repo = WorkExperienceRepository(db)
    await exp_repo.delete_all_for_user(uuid.UUID(user_id))
    for i, exp in enumerate(data.experiences):
        entry = WorkExperience(
            user_id=uuid.UUID(user_id),
            company=exp.company,
            role=exp.role,
            location=exp.location,
            description=exp.description,
            start_date=date.fromisoformat(exp.start_date) if exp.start_date else None,
            end_date=date.fromisoformat(exp.end_date) if exp.end_date and not exp.is_current else None,
            is_current=exp.is_current,
            sort_order=i,
        )
        await exp_repo.create(entry)

    # Also keep denormalized fields for backward compat (first current entry)
    current_exp = next((e for e in data.experiences if e.is_current), None)
    if not current_exp and data.experiences:
        current_exp = data.experiences[0]

    updates = {
        "current_company": current_exp.company if current_exp else data.current_company,
        "current_title": current_exp.role if current_exp else data.current_title,
        "years_of_experience": data.years_of_experience,
        "headline": data.headline,
        "summary": data.summary,
        "experience_level": data.experience_level,
        "notice_period_days": data.notice_period_days,
        "work_authorization": data.work_authorization,
    }
    _advance_step(updates, user.onboarding_step, 2)
    await repo.update(user, updates)
    await db.commit()
    return {"message": "Step 2 saved", "step": 2, "experiences_saved": len(data.experiences)}


@router.post("/step/3")
async def save_step_3(
    data: OnboardingStep3Request,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Step 3: Salary & Compensation."""
    repo = UserRepository(db)
    user = await repo.get_by_id(uuid.UUID(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Compute CTC = base + bonus + RSU
    base = data.current_salary_base or 0
    bonus = data.current_salary_bonus or 0
    rsu = data.current_salary_rsu or 0
    ctc = base + bonus + rsu

    updates = {
        "current_salary_base": data.current_salary_base,
        "current_salary_bonus": data.current_salary_bonus,
        "current_salary_rsu": data.current_salary_rsu,
        "current_salary_ctc": ctc if ctc > 0 else None,
        "salary_currency": data.salary_currency,
        "expected_salary_min": data.expected_salary_min,
        "expected_salary_max": data.expected_salary_max,
    }
    _advance_step(updates, user.onboarding_step, 3)
    await repo.update(user, updates)
    await db.commit()
    return {"message": "Step 3 saved", "step": 3}


@router.post("/step/4")
async def save_step_4(
    data: OnboardingStep4Request,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Step 4: Skills."""
    repo = UserRepository(db)
    user = await repo.get_by_id(uuid.UUID(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    classified = data.classified_skills
    if not classified and data.raw_skills:
        # Auto-classify via LLM
        llm = LLMService()
        classified = await llm.classify_skills(data.raw_skills)

    updates: dict = {}
    if classified:
        updates["classified_skills"] = json.dumps(classified)
        # Also flatten into the legacy skills field
        all_skills = [s for skills in classified.values() for s in skills]
        updates["skills"] = json.dumps(all_skills)

    _advance_step(updates, user.onboarding_step, 4)
    await repo.update(user, updates)
    await db.commit()
    return {"message": "Step 4 saved", "step": 4, "classified_skills": classified}


@router.post("/step/5")
async def save_step_5(
    data: OnboardingStep5Request,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Step 5: Job Preferences."""
    repo = UserRepository(db)
    user = await repo.get_by_id(uuid.UUID(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    updates: dict = {
        "preferred_location": data.preferred_location,
        "job_search_keywords": data.job_search_keywords,
        "willing_to_relocate": data.willing_to_relocate,
        "remote_preference": data.remote_preference,
        "job_type_preference": data.job_type_preference,
    }
    if data.target_roles is not None:
        updates["target_roles"] = json.dumps(data.target_roles)
    if data.preferred_technologies is not None:
        updates["preferred_technologies"] = json.dumps(data.preferred_technologies)
    if data.preferred_companies is not None:
        updates["preferred_companies"] = json.dumps(data.preferred_companies)

    _advance_step(updates, user.onboarding_step, 5)
    await repo.update(user, updates)
    await db.commit()
    return {"message": "Step 5 saved", "step": 5}


@router.post("/step/6")
async def save_step_6(
    data: OnboardingStep6Request,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Step 6: Platform Credentials."""
    repo = UserRepository(db)
    user = await repo.get_by_id(uuid.UUID(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check LinkedIn is provided
    has_linkedin = any(c.platform == "linkedin" for c in data.credentials)
    if not has_linkedin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="LinkedIn credentials are required",
        )

    updates: dict = {}
    for cred in data.credentials:
        encrypted = encrypt_credential(
            json.dumps({"username": cred.username, "password": cred.password})
        )
        field_name = f"encrypted_{cred.platform}_creds"
        updates[field_name] = encrypted

    _advance_step(updates, user.onboarding_step, 6)
    await repo.update(user, updates)
    await db.commit()

    return {
        "message": "Step 6 saved",
        "step": 6,
        "platforms_configured": [c.platform for c in data.credentials],
    }


@router.post("/step/7")
async def save_step_7(
    data: OnboardingStep7Request,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Step 7: Resume (LaTeX source). For PDF upload use /upload-resume."""
    if not data.latex_source:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume is required. Provide LaTeX source or use /upload-resume for PDF.",
        )

    repo = UserRepository(db)
    user = await repo.get_by_id(uuid.UUID(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Save as master resume
    resume_repo = ResumeRepository(db)
    existing_master = await resume_repo.get_master_resume(uuid.UUID(user_id))
    if existing_master:
        await resume_repo.update(existing_master, {"is_master": False})

    next_version = await resume_repo.get_next_version_number(uuid.UUID(user_id))
    resume = ResumeVersion(
        user_id=uuid.UUID(user_id),
        name="Master Resume (Onboarding)",
        latex_source=data.latex_source,
        is_master=True,
        version_number=next_version,
    )
    await resume_repo.create(resume)

    # Also store on user record
    updates: dict = {"master_resume_latex": data.latex_source}
    _advance_step(updates, user.onboarding_step, 7)
    await repo.update(user, updates)
    await db.commit()

    return {"message": "Step 7 saved", "step": 7, "resume_version_id": str(resume.id)}


@router.post("/step/8")
async def save_step_8(
    data: OnboardingStep8Request,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Step 8: Education & EEO — final step, marks onboarding complete."""
    repo = UserRepository(db)
    user = await repo.get_by_id(uuid.UUID(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Save structured education to normalized table
    edu_repo = EducationRepository(db)
    await edu_repo.delete_all_for_user(uuid.UUID(user_id))
    for i, edu in enumerate(data.education):
        entry = Education(
            user_id=uuid.UUID(user_id),
            degree=edu.degree,
            custom_degree=edu.custom_degree if edu.degree == "Other" else None,
            field_of_study=edu.field_of_study,
            custom_field=edu.custom_field if edu.field_of_study == "Other" else None,
            institution=edu.institution,
            start_year=edu.start_year,
            end_year=edu.end_year,
            gpa=float(edu.gpa) if edu.gpa else None,
            gpa_scale=edu.gpa_scale,
            activities=edu.activities,
            sort_order=i,
        )
        await edu_repo.create(entry)

    # Keep legacy JSON for backward compat
    education_json = json.dumps([e.model_dump() for e in data.education]) if data.education else None

    updates: dict = {
        "education": education_json,
        "disability_status": data.disability_status,
        "veteran_status": data.veteran_status,
        "cover_letter_default": data.cover_letter_default,
        "onboarding_step": 8,
        "onboarding_completed": True,
    }
    await repo.update(user, updates)
    await db.commit()

    logger.info("Onboarding completed", user_id=user_id)
    return {"message": "Onboarding complete!", "step": 8, "completed": True}


# ── Skill Classification ────────────────────────────────────────


@router.post("/classify-skills", response_model=SkillClassificationResponse)
async def classify_skills(
    data: SkillClassificationRequest,
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001
):
    """Classify raw skills into fixed categories via LLM."""
    llm = LLMService()
    classified = await llm.classify_skills(data.skills)
    return SkillClassificationResponse(classified=classified)


# ── Resume Upload (PDF) ─────────────────────────────────────────


@router.post("/upload-resume", response_model=ResumeUploadResponse)
async def upload_resume(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a PDF resume → extract text → LLM converts to LaTeX → store as master.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are accepted",
        )

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10 MB limit
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum 10 MB.",
        )

    # Extract text from PDF
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(content)) as pdf:
            pages_text = [page.extract_text() or "" for page in pdf.pages]
            extracted_text = "\n\n".join(pages_text).strip()
    except Exception as e:
        logger.error("PDF text extraction failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not extract text from PDF: {e}",
        ) from e

    if not extracted_text or len(extracted_text) < 50:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="PDF appears to be empty or contains too little text. "
                   "Try pasting LaTeX source directly instead.",
        )

    # Convert to LaTeX via LLM
    llm = LLMService()
    latex_source = await llm.pdf_to_latex(extracted_text)

    if not latex_source or "\\documentclass" not in latex_source:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not convert PDF to valid LaTeX. Try pasting LaTeX source directly.",
        )

    # Save as master resume
    repo = UserRepository(db)
    user = await repo.get_by_id(uuid.UUID(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    resume_repo = ResumeRepository(db)
    existing_master = await resume_repo.get_master_resume(uuid.UUID(user_id))
    if existing_master:
        await resume_repo.update(existing_master, {"is_master": False})

    next_version = await resume_repo.get_next_version_number(uuid.UUID(user_id))
    resume = ResumeVersion(
        user_id=uuid.UUID(user_id),
        name="Master Resume (PDF Upload)",
        latex_source=latex_source,
        is_master=True,
        version_number=next_version,
    )
    await resume_repo.create(resume)

    # Update user
    updates: dict = {"master_resume_latex": latex_source}
    _advance_step(updates, user.onboarding_step, 7)
    await repo.update(user, updates)
    await db.commit()

    return ResumeUploadResponse(
        latex_source=latex_source,
        method="pdf_converted",
        compilation_status="pending",
    )


# ── Summary ──────────────────────────────────────────────────────


@router.get("/summary", response_model=OnboardingSummaryResponse)
async def get_onboarding_summary(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get a summary of all onboarding data collected so far."""
    repo = UserRepository(db)
    user = await repo.get_by_id(uuid.UUID(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    classified = None
    if user.classified_skills:
        try:
            classified = json.loads(user.classified_skills)
        except json.JSONDecodeError:
            pass

    target_roles = None
    if user.target_roles:
        try:
            target_roles = json.loads(user.target_roles)
        except json.JSONDecodeError:
            pass

    education_count = 0
    if user.education:
        try:
            education_count = len(json.loads(user.education))
        except json.JSONDecodeError:
            pass

    return OnboardingSummaryResponse(
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        headline=user.headline,
        current_company=user.current_company,
        current_title=user.current_title,
        years_of_experience=user.years_of_experience,
        experience_level=user.experience_level,
        salary_currency=user.salary_currency,
        current_salary_ctc=user.current_salary_ctc,
        expected_salary_min=user.expected_salary_min,
        expected_salary_max=user.expected_salary_max,
        classified_skills=classified,
        target_roles=target_roles,
        preferred_location=user.preferred_location,
        remote_preference=user.remote_preference,
        has_linkedin_creds=bool(user.encrypted_linkedin_creds),
        has_indeed_creds=bool(user.encrypted_indeed_creds),
        has_naukri_creds=bool(user.encrypted_naukri_creds),
        has_resume=bool(user.master_resume_latex),
        education_count=education_count,
        onboarding_completed=user.onboarding_completed,
    )


# ── Helpers ──────────────────────────────────────────────────────


def _advance_step(updates: dict, current_step: int | None, step_number: int) -> None:
    """Only advance onboarding_step if we're at or past this step for the first time."""
    if (current_step or 0) < step_number:
        updates["onboarding_step"] = step_number
