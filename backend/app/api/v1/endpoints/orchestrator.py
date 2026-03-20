"""
Autonomous Orchestrator Endpoint

One-click pipeline: scrape → score → tailor → apply.
Chains agent outputs together into a fully autonomous job search flow.
"""

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.agent_execution import AgentExecution
from app.repositories.agent_execution_repo import AgentExecutionRepository
from app.repositories.subscription_repo import SubscriptionRepository

router = APIRouter()


class OrchestratorRunRequest(BaseModel):
    """Configure the autonomous pipeline."""
    scrape_keywords: list[str] = Field(default_factory=list)
    scrape_location: str | None = None
    max_applications: int = Field(default=5, ge=1, le=50)
    auto_tailor: bool = True
    auto_apply: bool = True
    dry_run: bool = False  # If true, plan but don't execute


class OrchestratorStepResult(BaseModel):
    step: str
    status: str  # planned, running, success, failed, skipped
    message: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class OrchestratorResponse(BaseModel):
    pipeline_id: str
    status: str  # planned, running, completed, partial_failure
    steps: list[OrchestratorStepResult]
    total_jobs_found: int = 0
    total_matched: int = 0
    total_tailored: int = 0
    total_applied: int = 0


@router.post("/run", response_model=OrchestratorResponse)
async def run_autonomous_pipeline(
    body: OrchestratorRunRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Run the full autonomous job search pipeline.

    Steps:
    1. Scrape jobs based on keywords/location
    2. Score & rank jobs against master resume
    3. Tailor resume for top matches
    4. Auto-apply to matched jobs

    Requires Enterprise plan for full autonomous mode.
    """
    # Check subscription for autonomous access
    sub_repo = SubscriptionRepository(db)
    sub = await sub_repo.get_by_user(uuid.UUID(user_id))
    if sub and not sub.autonomous_mode_enabled:
        raise HTTPException(
            status_code=403,
            detail="Autonomous mode requires Enterprise plan. Upgrade to access this feature.",
        )

    pipeline_id = str(uuid.uuid4())
    steps: list[OrchestratorStepResult] = []

    # Record pipeline execution
    execution = AgentExecution(
        id=uuid.UUID(pipeline_id),
        user_id=uuid.UUID(user_id),
        agent_name="autonomous_pipeline",
        status="running",
        params=json.dumps(body.model_dump()),
        started_at=datetime.now(UTC),
    )
    repo = AgentExecutionRepository(db)
    await repo.create(execution)
    await db.commit()

    totals = {"jobs_found": 0, "matched": 0, "tailored": 0, "applied": 0}

    if body.dry_run:
        # Plan mode — show what would happen
        steps = [
            OrchestratorStepResult(
                step="scrape",
                status="planned",
                message=f"Would scrape jobs for keywords: {body.scrape_keywords}",
                data={"keywords": body.scrape_keywords, "location": body.scrape_location},
            ),
            OrchestratorStepResult(
                step="score",
                status="planned",
                message="Would score all scraped jobs against master resume",
            ),
        ]
        if body.auto_tailor:
            steps.append(OrchestratorStepResult(
                step="tailor",
                status="planned",
                message=f"Would tailor resume for top {body.max_applications} matches",
            ))
        if body.auto_apply:
            steps.append(OrchestratorStepResult(
                step="apply",
                status="planned",
                message=f"Would auto-apply to up to {body.max_applications} jobs",
            ))

        execution.status = "success"
        execution.result = json.dumps({"mode": "dry_run", "steps": len(steps)})
        execution.completed_at = datetime.now(UTC)
        await db.commit()

        return OrchestratorResponse(
            pipeline_id=pipeline_id,
            status="planned",
            steps=steps,
        )

    # ── Step 1: Scrape Jobs ───────────────────────────────────
    try:
        from app.agents.orchestrator import get_orchestrator
        from app.agents.base import AgentContext
        from app.services.llm_service import LLMService

        orch = get_orchestrator()
        ctx = AgentContext(
            user_id=user_id,
            params={
                "keywords": body.scrape_keywords,
                "location": body.scrape_location,
            },
            db_session=db,
            llm_service=LLMService(),
        )

        scrape_result = await orch.dispatch("job_scraper", ctx)
        jobs_found = scrape_result.items_processed if scrape_result.success else 0
        totals["jobs_found"] = jobs_found

        steps.append(OrchestratorStepResult(
            step="scrape",
            status="success" if scrape_result.success else "failed",
            message=f"Found {jobs_found} new jobs" if scrape_result.success else "; ".join(scrape_result.errors or ["Scraping failed"]),
            data=scrape_result.data or {},
        ))
    except Exception as e:
        steps.append(OrchestratorStepResult(
            step="scrape",
            status="failed",
            message=str(e),
        ))

    # ── Step 2: Score & Rank ──────────────────────────────────
    try:
        score_result = await orch.dispatch("match_scorer", ctx)
        matched = score_result.items_processed if score_result.success else 0
        totals["matched"] = matched

        steps.append(OrchestratorStepResult(
            step="score",
            status="success" if score_result.success else "failed",
            message=f"Scored {matched} jobs" if score_result.success else "Scoring failed",
            data=score_result.data or {},
        ))
    except Exception as e:
        steps.append(OrchestratorStepResult(
            step="score",
            status="failed",
            message=str(e),
        ))

    # ── Step 3: Tailor Resumes ────────────────────────────────
    if body.auto_tailor:
        try:
            ctx.params["max_jobs"] = body.max_applications
            tailor_result = await orch.dispatch("resume_tailor", ctx)
            tailored = tailor_result.items_processed if tailor_result.success else 0
            totals["tailored"] = tailored

            steps.append(OrchestratorStepResult(
                step="tailor",
                status="success" if tailor_result.success else "failed",
                message=f"Tailored {tailored} resumes" if tailor_result.success else "Tailoring failed",
                data=tailor_result.data or {},
            ))
        except Exception as e:
            steps.append(OrchestratorStepResult(
                step="tailor",
                status="failed",
                message=str(e),
            ))

    # ── Step 4: Auto-Apply ────────────────────────────────────
    if body.auto_apply:
        try:
            ctx.params["max_applications"] = body.max_applications
            apply_result = await orch.dispatch("auto_applier", ctx)
            applied = apply_result.items_processed if apply_result.success else 0
            totals["applied"] = applied

            steps.append(OrchestratorStepResult(
                step="apply",
                status="success" if apply_result.success else "failed",
                message=f"Applied to {applied} jobs" if apply_result.success else "Application failed",
                data=apply_result.data or {},
            ))
        except Exception as e:
            steps.append(OrchestratorStepResult(
                step="apply",
                status="failed",
                message=str(e),
            ))

    # Finalize
    all_success = all(s.status == "success" for s in steps)
    any_success = any(s.status == "success" for s in steps)

    final_status = "completed" if all_success else ("partial_failure" if any_success else "failed")
    execution.status = "success" if all_success else "failed"
    execution.result = json.dumps({
        "steps": [s.model_dump() for s in steps],
        "totals": totals,
    })
    execution.completed_at = datetime.now(UTC)
    execution.items_processed = sum(totals.values())
    await db.commit()

    return OrchestratorResponse(
        pipeline_id=pipeline_id,
        status=final_status,
        steps=steps,
        total_jobs_found=totals["jobs_found"],
        total_matched=totals["matched"],
        total_tailored=totals["tailored"],
        total_applied=totals["applied"],
    )


@router.get("/status/{pipeline_id}")
async def get_pipeline_status(
    pipeline_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get status of a pipeline execution."""
    repo = AgentExecutionRepository(db)
    execution = await repo.get(uuid.UUID(pipeline_id))
    if not execution or str(execution.user_id) != user_id:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    return {
        "pipeline_id": str(execution.id),
        "status": execution.status,
        "agent_name": execution.agent_name,
        "started_at": execution.started_at.isoformat() if execution.started_at else None,
        "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
        "items_processed": execution.items_processed,
        "result": json.loads(execution.result) if execution.result else None,
    }
