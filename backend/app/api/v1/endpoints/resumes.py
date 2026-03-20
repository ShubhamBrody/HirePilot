"""
Resume Endpoints — CRUD, compilation, tailoring, templates, AI chat, parsing, diff, rollback.
"""

import json
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.repositories.resume_repo import ResumeRepository, ResumeTemplateRepository
from app.repositories.job_repo import JobRepository
from app.schemas.resume import (
    ResumeChatRequest,
    ResumeChatResponse,
    ResumeCompileResponse,
    ResumeListResponse,
    ResumeParseResponse,
    ResumeRollbackRequest,
    ResumeTemplateResponse,
    ResumeTailorRequest,
    ResumeTailorResponse,
    ResumeVersionCreateRequest,
    ResumeVersionResponse,
    ResumeVersionUpdateRequest,
    SpellingCheckRequest,
    SpellingCheckResponse,
    SpellingIssue,
    VersionDiffResponse,
)
from app.services.latex_compiler import LatexCompilerService
from app.services.llm_service import LLMService
from app.services.resume_service import ResumeService

router = APIRouter()


# ── CRUD ────────────────────────────────────────────────────────


@router.get("", response_model=ResumeListResponse)
async def list_resumes(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List all resume versions for the current user."""
    service = ResumeService(db)
    return await service.list_versions(user_id)


@router.post("", response_model=ResumeVersionResponse, status_code=status.HTTP_201_CREATED)
async def create_resume(
    data: ResumeVersionCreateRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Create a new resume version."""
    service = ResumeService(db)
    return await service.create_version(user_id, data)


@router.get("/master", response_model=ResumeVersionResponse | None)
async def get_master_resume(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get the user's master resume."""
    service = ResumeService(db)
    result = await service.get_master_resume(user_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No master resume found. Upload one first.",
        )
    return result


@router.get("/templates", response_model=list[ResumeTemplateResponse])
async def list_templates(db: AsyncSession = Depends(get_db)):
    """List available LaTeX resume templates."""
    repo = ResumeTemplateRepository(db)
    templates = await repo.get_active_templates()
    return [ResumeTemplateResponse.model_validate(t) for t in templates]


# ── Compile ─────────────────────────────────────────────────────


class CompilePreviewRequest(BaseModel):
    latex_source: str


@router.post("/compile-preview")
async def compile_preview(
    data: CompilePreviewRequest,
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001
):
    """Compile LaTeX source on-the-fly and return the PDF as bytes."""
    if not data.latex_source or not data.latex_source.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="LaTeX source is required",
        )

    compiler = LatexCompilerService()
    result = await compiler.compile(data.latex_source)

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "LaTeX compilation failed",
                "errors": result["errors"][:10],
            },
        )

    return Response(
        content=result["pdf_data"],
        media_type="application/pdf",
        headers={"Content-Disposition": "inline; filename=preview.pdf"},
    )


# ── AI Tailor (wired to Ollama) ─────────────────────────────────


@router.post("/tailor", response_model=ResumeTailorResponse)
async def tailor_resume(
    data: ResumeTailorRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    AI-tailor a resume for a specific job description.
    Auto-compiles the result and runs ATS scoring.
    Preserves the master resume's LaTeX preamble/structure.
    """
    resume_repo = ResumeRepository(db)
    job_repo = JobRepository(db)
    llm = LLMService()

    # Load base resume (or master)
    if data.base_resume_id:
        source_resume = await resume_repo.get_by_id(uuid.UUID(data.base_resume_id))
    else:
        source_resume = await resume_repo.get_master_resume(uuid.UUID(user_id))
    if not source_resume:
        raise HTTPException(status_code=404, detail="No base resume found")

    # Load job
    job = await job_repo.get_by_id(uuid.UUID(data.job_listing_id))
    if not job:
        raise HTTPException(status_code=404, detail="Job listing not found")

    # AI tailoring
    tailor_result = await llm.tailor_resume(
        master_latex=source_resume.latex_source,
        job_description=job.description,
        company=job.company,
        role=job.title,
    )
    tailored_latex = tailor_result.get("tailored_latex", source_resume.latex_source)

    # Preamble preservation: extract preamble from master and enforce it
    tailored_latex = _enforce_master_preamble(source_resume.latex_source, tailored_latex)

    # Generate changes summary
    changes = await llm.generate_changes_summary(source_resume.latex_source, tailored_latex)

    # Create new resume version
    from app.models.resume import ResumeVersion
    next_version = await resume_repo.get_next_version_number(uuid.UUID(user_id))
    new_version = ResumeVersion(
        user_id=uuid.UUID(user_id),
        name=f"Tailored for {job.title} @ {job.company}",
        latex_source=tailored_latex,
        is_master=False,
        version_number=next_version,
        tailored_for_job_id=job.id,
        ai_tailored=True,
        ai_changes_summary=changes.get("changes_summary", ""),
        target_company=job.company,
        target_role=job.title,
    )
    created = await resume_repo.create(new_version)

    # Auto-compile the tailored resume
    compile_status = "pending"
    compile_errors = None
    compiler = LatexCompilerService()
    compile_result = await compiler.compile(tailored_latex)
    if compile_result["success"]:
        compile_status = "success"
        await resume_repo.update(created, {
            "compilation_status": "success",
            "pdf_s3_key": compile_result.get("s3_key"),
        })
    else:
        compile_status = "error"
        compile_errors = compile_result.get("errors", [])[:5]
        await resume_repo.update(created, {
            "compilation_status": "error",
            "compilation_errors": json.dumps(compile_errors),
        })

    # Auto-ATS-score if we have a job description
    ats_score = None
    if job.description:
        try:
            score_data = await llm.score_resume_ats(tailored_latex, job.description)
            ats_score = score_data.get("overall_score", 0)
            await resume_repo.update(created, {"ats_score": ats_score})
        except Exception:
            pass  # Non-critical — don't fail the tailor if scoring fails

    await db.commit()

    return ResumeTailorResponse(
        resume_version_id=str(created.id),
        name=created.name,
        changes_summary=changes.get("changes_summary", ""),
        matched_keywords=changes.get("keywords_added", []),
        optimization_score=changes.get("optimization_score", 0.0),
        compilation_status=compile_status,
        compilation_errors=compile_errors,
        ats_score=ats_score,
    )


def _extract_preamble(latex: str) -> str:
    """Extract the LaTeX preamble (everything before \\begin{document})."""
    match = re.search(r"(.*?)(\\begin\{document\})", latex, re.DOTALL)
    if match:
        return match.group(1)
    return ""


def _enforce_master_preamble(master_latex: str, tailored_latex: str) -> str:
    """Replace the tailored resume's preamble with the master's preamble."""
    master_preamble = _extract_preamble(master_latex)
    if not master_preamble:
        return tailored_latex

    # Replace preamble in tailored version
    match = re.search(r"(.*?)(\\begin\{document\})", tailored_latex, re.DOTALL)
    if match:
        return master_preamble + "\\begin{document}" + tailored_latex[match.end():]
    return tailored_latex


# ── ATS Scoring ─────────────────────────────────────────────────


class ATSScoreRequest(BaseModel):
    resume_id: str | None = None  # If None, uses master resume
    job_id: str | None = None
    job_description: str | None = None  # Direct JD text, alternative to job_id


class ATSScoreResponse(BaseModel):
    overall_score: int = 0
    breakdown: dict = {}
    matched_keywords: list[str] = []
    missing_keywords: list[str] = []
    strengths: list[str] = []
    weaknesses: list[str] = []
    suggestions: list[str] = []
    summary: str = ""


@router.post("/ats-score", response_model=ATSScoreResponse)
async def score_resume_ats(
    data: ATSScoreRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Score a resume against a job description for ATS compatibility.
    Returns a 0-100 score with breakdown and suggestions.
    """
    from app.agents.ats_scoring_agent import ATSScoringAgent
    from app.agents.base import AgentContext

    agent = ATSScoringAgent()
    context = AgentContext(
        user_id=user_id,
        params={
            "resume_id": data.resume_id,
            "job_id": data.job_id,
            "job_description": data.job_description,
        },
        db_session=db,
        llm_service=LLMService(),
    )

    result = await agent.run(context)

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=result.errors[0] if result.errors else "ATS scoring failed",
        )

    return ATSScoreResponse(
        overall_score=result.data.get("overall_score", 0),
        breakdown=result.data.get("breakdown", {}),
        matched_keywords=result.data.get("matched_keywords", []),
        missing_keywords=result.data.get("missing_keywords", []),
        strengths=result.data.get("strengths", []),
        weaknesses=result.data.get("weaknesses", []),
        suggestions=result.data.get("suggestions", []),
        summary=result.data.get("summary", ""),
    )


# ── AI Chat ─────────────────────────────────────────────────────


@router.post("/chat", response_model=ResumeChatResponse)
async def resume_chat(
    data: ResumeChatRequest,
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
):
    """
    AI chat interface for the resume editor.
    User sends a message; AI returns updated LaTeX + explanation.
    """
    resume_repo = ResumeRepository(db)
    resume = await resume_repo.get_by_id(uuid.UUID(data.resume_id))
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    llm = LLMService()
    result = await llm.chat_resume(
        resume_latex=resume.latex_source,
        user_message=data.message,
        history=data.history,
    )

    updated_latex = result.get("updated_latex")
    explanation = result.get("explanation", "No changes made.")

    # If AI returned updated LaTeX, save it
    if updated_latex and updated_latex.strip():
        resume.latex_source = updated_latex
        await db.commit()

    return ResumeChatResponse(
        updated_latex=updated_latex,
        explanation=explanation,
    )


# ── Resume Parsing ──────────────────────────────────────────────


@router.post("/{resume_id}/parse", response_model=ResumeParseResponse)
async def parse_resume(
    resume_id: str,
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
):
    """Parse a resume into structured sections using AI."""
    resume_repo = ResumeRepository(db)
    resume = await resume_repo.get_by_id(uuid.UUID(resume_id))
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    llm = LLMService()
    parsed = await llm.parse_resume(resume.latex_source)

    # Store parsed sections on the resume
    resume.parsed_sections = json.dumps(parsed)
    await db.commit()

    return ResumeParseResponse(
        resume_id=str(resume.id),
        parsed_sections=parsed,
    )


# ── Version Diff ────────────────────────────────────────────────


@router.get("/diff/{version_a_id}/{version_b_id}", response_model=VersionDiffResponse)
async def diff_versions(
    version_a_id: str,
    version_b_id: str,
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
):
    """Compare two resume versions using AI and return a summary of changes."""
    resume_repo = ResumeRepository(db)
    version_a = await resume_repo.get_by_id(uuid.UUID(version_a_id))
    version_b = await resume_repo.get_by_id(uuid.UUID(version_b_id))
    if not version_a or not version_b:
        raise HTTPException(status_code=404, detail="One or both versions not found")

    llm = LLMService()
    diff = await llm.generate_changes_summary(version_a.latex_source, version_b.latex_source)

    return VersionDiffResponse(
        version_a_id=version_a_id,
        version_b_id=version_b_id,
        changes_summary=diff.get("changes_summary", ""),
        sections_modified=diff.get("sections_modified", []),
        keywords_added=diff.get("keywords_added", []),
        optimization_score=diff.get("optimization_score", 0.0),
    )


# ── Rollback ────────────────────────────────────────────────────


@router.post("/rollback", response_model=ResumeVersionResponse)
async def rollback_resume(
    data: ResumeRollbackRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Rollback to a previous resume version by creating a new version
    with the content of the target version.
    """
    resume_repo = ResumeRepository(db)
    target = await resume_repo.get_by_id(uuid.UUID(data.target_version_id))
    if not target:
        raise HTTPException(status_code=404, detail="Target version not found")

    from app.models.resume import ResumeVersion
    next_version = await resume_repo.get_next_version_number(uuid.UUID(user_id))
    rollback_version = ResumeVersion(
        user_id=uuid.UUID(user_id),
        name=f"Rollback to v{target.version_number}",
        description=f"Rolled back from v{target.version_number}: {target.name}",
        latex_source=target.latex_source,
        version_number=next_version,
        is_master=target.is_master,
        target_company=target.target_company,
        target_role=target.target_role,
        focus_area=target.focus_area,
        technologies=target.technologies,
        parsed_sections=target.parsed_sections,
    )
    created = await resume_repo.create(rollback_version)
    await db.commit()

    return ResumeVersionResponse.model_validate(created)


# ── Single Resume CRUD ──────────────────────────────────────────


@router.get("/{resume_id}", response_model=ResumeVersionResponse)
async def get_resume(
    resume_id: str,
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
):
    """Get a specific resume version."""
    try:
        service = ResumeService(db)
        return await service.get_version(resume_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{resume_id}", response_model=ResumeVersionResponse)
async def update_resume(
    resume_id: str,
    data: ResumeVersionUpdateRequest,
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
):
    """Update a resume version."""
    try:
        service = ResumeService(db)
        return await service.update_version(resume_id, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume(
    resume_id: str,
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
):
    """Delete a resume version."""
    try:
        service = ResumeService(db)
        await service.delete_version(resume_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{resume_id}/compile", response_model=ResumeCompileResponse)
async def compile_resume(
    resume_id: str,
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
):
    """Trigger LaTeX-to-PDF compilation for a resume version."""
    try:
        service = ResumeService(db)
        return await service.compile_resume(resume_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ── Spelling / Grammar Check ───────────────────────────────────


@router.post("/spelling-check", response_model=SpellingCheckResponse)
async def check_spelling(
    data: SpellingCheckRequest,
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
):
    """
    LLM-based spelling and grammar check for a resume.
    Ignores proper nouns, names, emails, URLs, and LaTeX commands.
    """
    resume_repo = ResumeRepository(db)
    resume = await resume_repo.get_by_id(uuid.UUID(data.resume_id))
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    llm = LLMService()
    result = await llm.check_spelling_grammar(resume.latex_source)

    issues = [
        SpellingIssue(
            original=issue.get("original", ""),
            suggested=issue.get("suggested", ""),
            context=issue.get("context", ""),
            issue_type=issue.get("issue_type", "spelling"),
        )
        for issue in result.get("issues", [])
    ]

    return SpellingCheckResponse(
        issues=issues,
        total_issues=len(issues),
        corrected_latex=result.get("corrected_latex"),
    )
