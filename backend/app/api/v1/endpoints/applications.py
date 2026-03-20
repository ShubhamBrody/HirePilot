"""
Application Endpoints — CRUD, status management, auto-apply, analytics,
and guided Apply Wizard flow.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.application import Application, ApplicationMethod, ApplicationStatus
from app.repositories.application_repo import ApplicationRepository
from app.repositories.job_repo import JobRepository
from app.repositories.resume_repo import ResumeRepository
from app.schemas.application import (
    ApplicationAnalytics,
    ApplicationCreateRequest,
    ApplicationFilters,
    ApplicationListResponse,
    ApplicationResponse,
    ApplicationStatusUpdateRequest,
    AutoApplyRequest,
    WizardApproveRequest,
    WizardApproveResponse,
    WizardAutoApplyRequest,
    WizardAutoApplyResponse,
    WizardChatRequest,
    WizardChatResponse,
    WizardStartRequest,
    WizardStartResponse,
    WizardTailorRequest,
    WizardTailorResponse,
)
from app.services.application_service import ApplicationService
from app.services.llm_service import LLMService

router = APIRouter()


@router.get("", response_model=ApplicationListResponse)
async def list_applications(
    filters: ApplicationFilters = Depends(),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List the user's job applications with filtering."""
    service = ApplicationService(db)
    return await service.list_applications(user_id, filters)


@router.post("", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application(
    data: ApplicationCreateRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Create a new job application."""
    try:
        service = ApplicationService(db)
        return await service.create_application(user_id, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/{application_id}/status", response_model=ApplicationResponse)
async def update_application_status(
    application_id: str,
    data: ApplicationStatusUpdateRequest,
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
):
    """Update an application's status (Applied, Interview, Offer, etc.)."""
    try:
        service = ApplicationService(db)
        return await service.update_status(application_id, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/analytics", response_model=ApplicationAnalytics)
async def get_analytics(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get application analytics and statistics."""
    service = ApplicationService(db)
    return await service.get_analytics(user_id)


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(
    application_id: str,
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete an application (moves to trash)."""
    repo = ApplicationRepository(db)
    app = await repo.get_by_id(uuid.UUID(application_id))
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    await repo.soft_delete(app)
    await db.commit()


# ── Apply Wizard Flow ────────────────────────────────────────────


@router.post("/wizard/start", response_model=WizardStartResponse)
async def wizard_start(
    data: WizardStartRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Step 1: Start the guided apply wizard.
    Returns a description of what the system will do, asking for approval.
    """
    job_repo = JobRepository(db)
    job = await job_repo.get_by_id(uuid.UUID(data.job_listing_id))
    if not job:
        raise HTTPException(status_code=404, detail="Job listing not found")

    wizard_id = str(uuid.uuid4())

    return WizardStartResponse(
        wizard_id=wizard_id,
        job_title=job.title,
        company=job.company,
        job_description=job.description[:2000] if job.description else None,
        message=(
            f"I'm going to tailor your resume specifically for the "
            f"**{job.title}** position at **{job.company}**. "
            f"I'll analyze the job description, match your skills, "
            f"and optimize your resume for ATS systems. "
            f"Shall I proceed?"
        ),
        step="confirm_tailor",
    )


@router.post("/wizard/tailor", response_model=WizardTailorResponse)
async def wizard_tailor(
    data: WizardTailorRequest,
    job_listing_id: str = "",
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Step 2: AI tailors the resume for the job.
    Accepts job_listing_id as a query parameter.
    Returns the tailored LaTeX for user review.
    """
    if not job_listing_id:
        raise HTTPException(
            status_code=400,
            detail="job_listing_id query parameter is required",
        )

    resume_repo = ResumeRepository(db)
    job_repo = JobRepository(db)

    # Get base resume (specified or master)
    if data.base_resume_id:
        resume = await resume_repo.get_by_id(uuid.UUID(data.base_resume_id))
    else:
        resume = await resume_repo.get_master_resume(uuid.UUID(user_id))

    if not resume:
        raise HTTPException(
            status_code=404,
            detail="No resume found. Upload a master resume first.",
        )

    job = await job_repo.get_by_id(uuid.UUID(job_listing_id))
    if not job:
        raise HTTPException(status_code=404, detail="Job listing not found")

    # Tailor with LLM
    llm = LLMService()
    tailor_result = await llm.tailor_resume(
        master_latex=resume.latex_source,
        job_description=job.description,
        company=job.company,
        role=job.title,
    )

    tailored_latex = tailor_result.get("tailored_latex", resume.latex_source)
    compile_success = tailor_result.get("compile_success", True)

    # Get changes summary
    changes = await llm.generate_changes_summary(
        original=resume.latex_source,
        tailored=tailored_latex,
    )

    return WizardTailorResponse(
        wizard_id=data.wizard_id,
        tailored_latex=tailored_latex,
        changes_summary=changes.get("changes_summary"),
        sections_modified=changes.get("sections_modified", []),
        keywords_added=changes.get("keywords_added", []),
        compile_success=compile_success,
        message=(
            f"Here's your tailored resume for **{job.title}** at **{job.company}**. "
            f"I've {changes.get('changes_summary', 'optimized it for this role')}. "
            f"Review the changes and let me know if you'd like any modifications, "
            f"or approve it to proceed with the application."
        ),
        step="review_resume",
    )


@router.post("/wizard/chat", response_model=WizardChatResponse)
async def wizard_chat(
    data: WizardChatRequest,
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),  # noqa: ARG001
):
    """
    Step 2b: User requests modifications via chat.
    AI returns an updated resume based on the user's message.
    """
    llm = LLMService()
    result = await llm.chat_resume(
        resume_latex=data.current_latex,
        user_message=data.message,
        history=data.history or None,
    )

    return WizardChatResponse(
        wizard_id=data.wizard_id,
        updated_latex=result.get("updated_latex"),
        explanation=result.get("explanation", "Changes applied."),
        compile_success=bool(result.get("compile_success", True)),
        step="review_resume",
    )


@router.post("/wizard/approve", response_model=WizardApproveResponse)
async def wizard_approve(
    data: WizardApproveRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Step 3: User approves the resume. System saves it and creates an application.
    """
    resume_repo = ResumeRepository(db)
    job_repo = JobRepository(db)
    app_repo = ApplicationRepository(db)

    job = await job_repo.get_by_id(uuid.UUID(data.job_listing_id))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    uid = uuid.UUID(user_id)

    # Save the tailored resume as a new version
    from app.models.resume import ResumeVersion

    resume_name = data.resume_name or f"Tailored - {job.title} @ {job.company}"
    resume = ResumeVersion(
        user_id=uid,
        name=resume_name,
        latex_source=data.final_latex,
        is_master=False,
    )
    resume = await resume_repo.create(resume)

    # Create the application, linked to this resume
    application = Application(
        user_id=uid,
        job_listing_id=uuid.UUID(data.job_listing_id),
        resume_version_id=resume.id,
        company=job.company,
        role=job.title,
        job_description_snapshot=job.description,
        status=ApplicationStatus.DRAFT,
        method=ApplicationMethod.AUTOMATED,
    )
    application = await app_repo.create(application)
    await db.commit()

    return WizardApproveResponse(
        wizard_id=data.wizard_id,
        application_id=str(application.id),
        resume_version_id=str(resume.id),
        message=(
            f"Resume saved as **{resume_name}** and linked to your application. "
            f"I'm ready to apply to **{job.title}** at **{job.company}** "
            f"using browser automation. I'll navigate to the job page, "
            f"fill in your details, and submit the application. "
            f"Shall I proceed?"
        ),
        step="confirm_apply",
    )


@router.post("/wizard/apply", response_model=WizardAutoApplyResponse)
async def wizard_auto_apply(
    data: WizardAutoApplyRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),  # noqa: ARG001
):
    """
    Step 4: User approves — kick off Selenium-based auto-apply.
    """
    from app.tasks.automation import auto_apply_job

    task = auto_apply_job.delay(user_id, data.application_id, {})
    return WizardAutoApplyResponse(
        application_id=data.application_id,
        task_id=task.id,
        message=(
            "Application process started! I'm navigating to the job page "
            "and filling in your details. This may take a minute. "
            "You can check the status below."
        ),
        step="applying",
    )


# ── Dynamic path routes (must come AFTER static /wizard/* routes) ─


@router.post("/{application_id}/apply", status_code=status.HTTP_202_ACCEPTED)
async def auto_apply(
    application_id: str,
    data: AutoApplyRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),  # noqa: ARG001
) -> dict[str, str]:
    """
    Trigger automated job application via browser automation.
    Returns immediately — the Celery task handles the actual submission.
    """
    from app.tasks.automation import auto_apply_job

    task = auto_apply_job.delay(user_id, application_id, data.model_dump())
    return {
        "message": "Auto-apply task queued",
        "application_id": application_id,
        "task_id": task.id,
    }


@router.get("/{application_id}/resume")
async def get_application_resume(
    application_id: str,
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
):
    """
    Get the resume that was used for a specific application.
    Useful when preparing for interviews.
    """
    app_repo = ApplicationRepository(db)
    resume_repo = ResumeRepository(db)

    application = await app_repo.get_by_id(uuid.UUID(application_id))
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    resume = await resume_repo.get_by_id(application.resume_version_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume version not found")

    return {
        "application_id": str(application.id),
        "resume_version_id": str(resume.id),
        "resume_name": resume.name,
        "latex_source": resume.latex_source,
        "company": application.company,
        "role": application.role,
    }
