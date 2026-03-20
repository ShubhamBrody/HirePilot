"""
Agent Orchestrator

Central coordinator for all HirePilot AI agents.
Manages agent registry, dispatch, pipelines, and execution history.
"""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentContext, AgentResult, AgentStatus, BaseAgent
from app.core.logging import get_logger

logger = get_logger(__name__)


class AgentOrchestrator:
    """
    Singleton-style orchestrator that holds the agent registry
    and dispatches tasks to the correct agent.
    """

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    # ── Registry ─────────────────────────────────────────────

    def register(self, agent: BaseAgent) -> None:
        self._agents[agent.name] = agent
        logger.info("Agent registered", agent=agent.name)

    def get_agent(self, name: str) -> BaseAgent | None:
        return self._agents.get(name)

    def list_agents(self) -> list[dict[str, Any]]:
        return [a.get_info() for a in self._agents.values()]

    # ── Dispatch ─────────────────────────────────────────────

    async def dispatch(self, agent_name: str, context: AgentContext) -> AgentResult:
        agent = self._agents.get(agent_name)
        if not agent:
            return AgentResult(success=False, errors=[f"Unknown agent: {agent_name}"])
        if not agent.enabled:
            return AgentResult(success=False, errors=[f"Agent {agent_name} is disabled"])
        return await agent.run(context)

    async def run_pipeline(
        self,
        steps: list[dict[str, Any]],
        context: AgentContext,
    ) -> list[AgentResult]:
        """
        Run a sequence of agents. Each step is {"agent": "name", "params": {...}}.
        Stops on first failure unless step has "continue_on_failure": True.
        """
        results: list[AgentResult] = []
        for step in steps:
            agent_name = step["agent"]
            step_params = step.get("params", {})
            ctx = AgentContext(
                user_id=context.user_id,
                params={**context.params, **step_params},
                db_session=context.db_session,
                llm_service=context.llm_service,
            )
            result = await self.dispatch(agent_name, ctx)
            results.append(result)
            if not result.success and not step.get("continue_on_failure", False):
                logger.warning("Pipeline halted", failed_agent=agent_name)
                break
        return results

    # ── Status ───────────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        running = [n for n, a in self._agents.items() if a.status == AgentStatus.RUNNING]
        return {
            "total_agents": len(self._agents),
            "running": running,
            "agents": self.list_agents(),
        }

    def toggle_agent(self, name: str, enabled: bool) -> bool:
        agent = self._agents.get(name)
        if not agent:
            return False
        agent.enabled = enabled
        return True


# ── Singleton ────────────────────────────────────────────────

_orchestrator: AgentOrchestrator | None = None


def get_orchestrator() -> AgentOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
        _register_all_agents(_orchestrator)
    return _orchestrator


def _register_all_agents(orch: AgentOrchestrator) -> None:
    """Import and register every agent."""
    from app.agents.application_agent import ApplicationAgent
    from app.agents.ats_scoring_agent import ATSScoringAgent
    from app.agents.email_checker_agent import EmailCheckerAgent
    from app.agents.job_search_agent import JobSearchAgent
    from app.agents.linkedin_message_agent import LinkedInMessageAgent
    from app.agents.linkedin_reply_agent import LinkedInReplyAgent
    from app.agents.recommendations_agent import RecommendationsAgent
    from app.agents.recruiter_search_agent import RecruiterSearchAgent
    from app.agents.resume_tailor_agent import ResumeTailorAgent
    from app.agents.salary_negotiator_agent import SalaryNegotiatorAgent
    from app.agents.web_scraper_agent import WebScraperAgent

    for cls in (
        JobSearchAgent,
        RecruiterSearchAgent,
        ResumeTailorAgent,
        ApplicationAgent,
        WebScraperAgent,
        EmailCheckerAgent,
        RecommendationsAgent,
        SalaryNegotiatorAgent,
        LinkedInMessageAgent,
        LinkedInReplyAgent,
        ATSScoringAgent,
    ):
        orch.register(cls())
