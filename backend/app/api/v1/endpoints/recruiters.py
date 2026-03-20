"""
Recruiter Endpoints — Discovery, outreach, messaging.
"""

import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger

logger = get_logger(__name__)
from app.core.security import get_current_user_id, decrypt_credential
from app.models.recruiter import ConnectionStatus, OutreachMessage, OutreachStatus, Recruiter
from app.repositories.recruiter_repo import OutreachMessageRepository, RecruiterRepository
from app.repositories.user_repo import UserRepository
from app.schemas.recruiter import (
    FindRecruitersRequest,
    FindRecruitersResponse,
    GenerateMessageRequest,
    GenerateMessageResponse,
    OutreachMessageRequest,
    OutreachMessageResponse,
    RecruiterListResponse,
    RecruiterResponse,
)
from app.services.llm_service import LLMService

router = APIRouter()


@router.get("", response_model=RecruiterListResponse)
async def list_recruiters(
    connection_status: ConnectionStatus | None = None,
    company: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List discovered recruiters, optionally filtered by company or status."""
    repo = RecruiterRepository(db)
    skip = (page - 1) * page_size
    recruiters = await repo.get_user_recruiters(
        uuid.UUID(user_id), skip=skip, limit=page_size,
        connection_status=connection_status, company=company,
    )
    return RecruiterListResponse(
        recruiters=[RecruiterResponse.model_validate(r) for r in recruiters],
        total=len(recruiters),
    )


@router.delete("/{recruiter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recruiter(
    recruiter_id: str,
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a recruiter (moves to trash)."""
    repo = RecruiterRepository(db)
    recruiter = await repo.get_by_id(uuid.UUID(recruiter_id))
    if not recruiter:
        raise HTTPException(status_code=404, detail="Recruiter not found")
    await repo.soft_delete(recruiter)
    await db.commit()


@router.get("/messages/all")
async def list_all_messages(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List all outreach messages for the current user, with recruiter details."""
    msg_repo = OutreachMessageRepository(db)
    rec_repo = RecruiterRepository(db)
    skip = (page - 1) * page_size
    messages = await msg_repo.get_user_messages(uuid.UUID(user_id), skip=skip, limit=page_size)

    result = []
    recruiter_cache: dict[str, Recruiter | None] = {}
    for m in messages:
        rid = str(m.recruiter_id)
        if rid not in recruiter_cache:
            recruiter_cache[rid] = await rec_repo.get_by_id(m.recruiter_id)
        rec = recruiter_cache[rid]
        result.append({
            "id": str(m.id),
            "recruiter_id": rid,
            "recruiter_name": rec.name if rec else "Unknown",
            "recruiter_company": rec.company if rec else "Unknown",
            "recruiter_title": rec.title if rec else "",
            "message_type": m.message_type,
            "subject": m.subject,
            "body": m.body,
            "ai_generated": m.ai_generated,
            "status": m.status.value if hasattr(m.status, "value") else str(m.status),
            "sent_at": m.sent_at.isoformat() if m.sent_at else None,
            "error_message": m.error_message,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        })
    return {"messages": result, "total": len(result)}


@router.get("/linkedin/test")
async def test_linkedin_connection(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Test if we can connect to LinkedIn with saved credentials."""
    import asyncio

    from app.services.linkedin_service import LinkedInService

    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(uuid.UUID(user_id))
    if not user or not user.encrypted_linkedin_creds:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No LinkedIn credentials saved. Go to Settings > Credentials to add them.",
        )

    try:
        creds = json.loads(decrypt_credential(user.encrypted_linkedin_creds))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to decrypt credentials. Please re-save them in Settings.",
        )

    username = creds.get("username", "")
    password = creds.get("password", "")
    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incomplete credentials. Please update in Settings.",
        )

    linkedin = LinkedInService()
    result = await asyncio.get_event_loop().run_in_executor(
        None, linkedin.test_connection, username, password
    )
    return result


@router.get("/linkedin/inbox")
async def fetch_linkedin_inbox(
    count: int = Query(5, ge=1, le=20),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Fetch recent LinkedIn messaging conversations using Selenium."""
    import asyncio

    from app.services.linkedin_service import LinkedInService

    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(uuid.UUID(user_id))
    if not user or not user.encrypted_linkedin_creds:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No LinkedIn credentials saved. Go to Settings > Credentials to add them.",
        )

    try:
        creds = json.loads(decrypt_credential(user.encrypted_linkedin_creds))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to decrypt credentials.",
        )

    username = creds.get("username", "")
    password = creds.get("password", "")
    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incomplete credentials.",
        )

    linkedin = LinkedInService()
    result = await asyncio.get_event_loop().run_in_executor(
        None, linkedin.fetch_recent_messages, username, password, count
    )
    return result


@router.post("/find", response_model=FindRecruitersResponse)
async def find_recruiters(
    data: FindRecruitersRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Discover recruiters at a target company.
    Tries authenticated LinkedIn people search first, falls back to LLM.
    """
    from app.agents.linkedin_helper import linkedin_search_people

    profiles: list[dict] = []
    source = "linkedin"

    # ── Step 1: Try LinkedIn authenticated search ──
    role_kw = data.role or "recruiter hiring manager"
    try:
        li_result = await linkedin_search_people(db, user_id, data.company, role_kw, max_results=10)
        if li_result.get("success") and len(li_result.get("people", [])) > 0:
            for p in li_result["people"]:
                profiles.append({
                    "id": uuid.uuid4(),
                    "name": p.get("name", "Unknown"),
                    "title": p.get("title", ""),
                    "company": data.company,
                    "linkedin_url": p.get("linkedin_url", ""),
                    "email": None,
                    "discovered_at": datetime.now(UTC),
                })
        else:
            error_msg = li_result.get("error") or li_result.get("message", "")
            logger.info(
                "LinkedIn people search returned no results",
                company=data.company,
                message=error_msg,
            )
    except Exception as e:
        logger.warning("LinkedIn people search failed", error=str(e), company=data.company)

    # ── Step 2: LLM verification — filter to actual recruiters ──
    if profiles:
        from app.services.llm_service import LLMService
        llm = LLMService()
        try:
            profiles = await llm.verify_recruiter_profiles(
                profiles, data.company, role_kw,
            )
        except Exception as e:
            logger.warning("LLM recruiter verification failed", error=str(e))

    # ── Step 3: If no verified results, return empty with helpful message ──
    if not profiles:
        # Check if user has LinkedIn credentials at all
        from app.agents.linkedin_helper import get_linkedin_credentials
        creds = await get_linkedin_credentials(db, user_id)
        if not creds:
            return FindRecruitersResponse(
                recruiters=[],
                total=0,
                source="none",
            )
        return FindRecruitersResponse(
            recruiters=[],
            total=0,
            source="linkedin",
        )

    # ── Step 4: Clear old recruiters for this company, then persist new ones ──
    repo = RecruiterRepository(db)
    deleted = await repo.delete_by_company(uuid.UUID(user_id), data.company)
    if deleted:
        logger.info("Cleared old recruiters", company=data.company, count=deleted)

    saved: list[Recruiter] = []
    for p in profiles:
        linkedin_url = p.get("linkedin_url")

        recruiter = Recruiter(
            id=p["id"],
            user_id=uuid.UUID(user_id),
            name=p["name"],
            title=p.get("title"),
            company=p.get("company", data.company),
            email=p.get("email"),
            linkedin_url=linkedin_url,
            connection_status=ConnectionStatus.NOT_CONNECTED,
            platform="linkedin",
            discovered_at=p.get("discovered_at", datetime.now(UTC)),
        )
        saved_recruiter = await repo.create(recruiter)
        saved.append(saved_recruiter)

    await db.commit()

    return FindRecruitersResponse(
        recruiters=[RecruiterResponse.model_validate(r) for r in saved],
        total=len(saved),
        source=source,
    )


@router.get("/{recruiter_id}", response_model=RecruiterResponse)
async def get_recruiter(
    recruiter_id: str,
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
):
    """Get a specific recruiter."""
    repo = RecruiterRepository(db)
    recruiter = await repo.get_by_id(uuid.UUID(recruiter_id))
    if not recruiter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recruiter not found")
    return RecruiterResponse.model_validate(recruiter)


@router.post("/{recruiter_id}/outreach", response_model=OutreachMessageResponse, status_code=status.HTTP_201_CREATED)
async def send_outreach(
    recruiter_id: str,
    data: OutreachMessageRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Send an outreach message to a recruiter.
    Generates AI message if no custom_message provided, then dispatches via Celery.
    """
    from app.models.recruiter import OutreachMessage

    repo = RecruiterRepository(db)
    recruiter = await repo.get_by_id(uuid.UUID(recruiter_id))
    if not recruiter:
        raise HTTPException(status_code=404, detail="Recruiter not found")

    # Generate message body
    body = data.custom_message
    ai_generated = False
    if not body:
        llm = LLMService()
        body = await llm.generate(
            f"Write a short, professional LinkedIn {data.message_type} message to "
            f"{recruiter.name} ({recruiter.title} at {recruiter.company}). "
            "Keep it under 300 characters. Be genuine and mention interest in opportunities."
        )
        ai_generated = True

    # Persist outreach message
    msg_repo = OutreachMessageRepository(db)
    msg = OutreachMessage(
        user_id=uuid.UUID(user_id),
        recruiter_id=uuid.UUID(recruiter_id),
        message_type=data.message_type,
        body=body,
        ai_generated=ai_generated,
        status=OutreachStatus.PENDING,
    )
    created = await msg_repo.create(msg)
    await db.commit()

    return OutreachMessageResponse.model_validate(created)


@router.get("/{recruiter_id}/messages", response_model=list[OutreachMessageResponse])
async def get_messages(
    recruiter_id: str,
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
):
    """Get all outreach messages sent to a recruiter."""
    repo = OutreachMessageRepository(db)
    messages = await repo.get_messages_for_recruiter(uuid.UUID(recruiter_id))
    return [OutreachMessageResponse.model_validate(m) for m in messages]


@router.post("/generate-message", response_model=GenerateMessageResponse)
async def generate_message(
    data: GenerateMessageRequest,
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
):
    """
    Preview an AI-generated outreach message without sending it.
    Uses Ollama LLM for personalized message generation.
    """
    repo = RecruiterRepository(db)
    recruiter = await repo.get_by_id(uuid.UUID(data.recruiter_id))
    if not recruiter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recruiter not found")

    # Build context for LLM
    job_context = ""
    if data.job_listing_id:
        from app.repositories.job_repo import JobRepository
        job_repo = JobRepository(db)
        job = await job_repo.get_by_id(uuid.UUID(data.job_listing_id))
        if job:
            job_context = f" regarding the {job.title} position"

    llm = LLMService()
    message = await llm.generate(
        f"Write a {data.tone} LinkedIn {data.message_type} message to "
        f"{recruiter.name} ({recruiter.title} at {recruiter.company}){job_context}. "
        "Keep it concise, professional, and personalized. Under 300 characters for connection requests."
    )

    return GenerateMessageResponse(
        suggested_message=message.strip(),
        recruiter_name=recruiter.name,
        company=recruiter.company,
        job_title=recruiter.title,
    )
