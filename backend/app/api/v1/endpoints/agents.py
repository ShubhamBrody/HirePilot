"""
Agent Endpoints - Orchestrator dashboard, agent dispatch, pipelines.
"""

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentContext
from app.agents.orchestrator import get_orchestrator
from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.agent_execution import AgentExecution
from app.repositories.agent_execution_repo import AgentExecutionRepository
from app.services.llm_service import LLMService

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────

class AgentRunRequest(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)

    class Config:
        extra = "allow"


class PipelineStep(BaseModel):
    agent: str
    params: dict[str, Any] = Field(default_factory=dict)
    continue_on_failure: bool = False


class PipelineRequest(BaseModel):
    steps: list[PipelineStep] | None = None
    agents: list[str] | None = None


class AgentToggleRequest(BaseModel):
    enabled: bool | None = None


# ── Endpoints ────────────────────────────────────────────────

@router.get("")
async def list_agents(
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001
):
    """List all registered agents with their status."""
    orch = get_orchestrator()
    return {"agents": orch.list_agents()}


@router.get("/status")
async def get_orchestrator_status(
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001
):
    """Get orchestrator dashboard: active tasks, agent health."""
    orch = get_orchestrator()
    raw = orch.get_status()
    agents_map = {a["name"]: {"enabled": a["enabled"], "status": a["status"]} for a in raw.get("agents", [])}
    return {
        "agents": agents_map,
        "total": raw.get("total_agents", 0),
        "enabled": sum(1 for a in raw.get("agents", []) if a["enabled"]),
        "running": len(raw.get("running", [])),
    }


@router.post("/{agent_name}/run")
async def run_agent(
    agent_name: str,
    body: AgentRunRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Dispatch a specific agent."""
    orch = get_orchestrator()
    agent = orch.get_agent(agent_name)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent '{agent_name}' not found")

    # Merge explicit params with any extra fields sent in body
    merged_params = {**body.params}
    extras = body.model_dump(exclude={"params"})
    for k, v in extras.items():
        if v is not None:
            merged_params[k] = v

    # Record execution
    execution = AgentExecution(
        id=uuid.uuid4(),
        user_id=uuid.UUID(user_id),
        agent_name=agent_name,
        status="running",
        params=json.dumps(merged_params),
        started_at=datetime.now(UTC),
    )
    repo = AgentExecutionRepository(db)
    await repo.create(execution)
    await db.commit()

    # Run the agent
    context = AgentContext(
        user_id=user_id,
        params=merged_params,
        db_session=db,
        llm_service=LLMService(),
    )
    result = await orch.dispatch(agent_name, context)

    # Update execution record
    execution.status = "success" if result.success else "failed"
    execution.result = json.dumps(result.data)
    execution.error_message = "; ".join(result.errors) if result.errors else None
    execution.items_processed = result.items_processed
    execution.duration_seconds = result.duration_seconds
    execution.completed_at = datetime.now(UTC)
    await db.commit()

    return {
        "success": result.success,
        "data": result.data,
        "errors": result.errors,
        "duration_seconds": result.duration_seconds,
        "items_processed": result.items_processed,
        "execution_id": str(execution.id),
    }


@router.post("/{agent_name}/toggle")
async def toggle_agent(
    agent_name: str,
    body: AgentToggleRequest | None = None,
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001
):
    """Enable or disable an agent. If no body, flips current state."""
    orch = get_orchestrator()
    agent = orch.get_agent(agent_name)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    new_state = (not agent.enabled) if (body is None or body.enabled is None) else body.enabled
    orch.toggle_agent(agent_name, new_state)
    return {"agent": agent_name, "enabled": new_state}


@router.post("/pipeline")
async def run_pipeline(
    body: PipelineRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Run a multi-step agent pipeline."""
    orch = get_orchestrator()
    context = AgentContext(
        user_id=user_id,
        params={},
        db_session=db,
        llm_service=LLMService(),
    )
    # Support both formats: {steps: [{agent, params}]} and {agents: ["name", ...]}
    if body.steps:
        steps = [s.model_dump() for s in body.steps]
    elif body.agents:
        steps = [{"agent": a, "params": {}, "continue_on_failure": True} for a in body.agents]
    else:
        raise HTTPException(status_code=400, detail="Provide 'steps' or 'agents'")
    results = await orch.run_pipeline(steps, context)

    return {
        "steps_completed": len(results),
        "steps_total": len(steps),
        "all_success": all(r.success for r in results),
        "results": [
            {
                "success": r.success,
                "data": r.data,
                "errors": r.errors,
                "duration": r.duration_seconds,
            }
            for r in results
        ],
    }


@router.get("/history")
async def get_execution_history(
    agent_name: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get agent execution history."""
    repo = AgentExecutionRepository(db)
    skip = (page - 1) * page_size
    execs = await repo.get_user_executions(
        uuid.UUID(user_id), agent_name=agent_name, skip=skip, limit=page_size
    )
    return {
        "executions": [
            {
                "id": str(e.id),
                "agent_name": e.agent_name,
                "status": e.status,
                "items_processed": e.items_processed,
                "duration_seconds": e.duration_seconds,
                "error_message": e.error_message,
                "started_at": e.started_at.isoformat() if e.started_at else None,
                "completed_at": e.completed_at.isoformat() if e.completed_at else None,
            }
            for e in execs
        ],
        "total": len(execs),
    }
