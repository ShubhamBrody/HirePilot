"""
Base Agent Framework

Defines the abstract base class, context, and result types
that every HirePilot AI agent must implement.
"""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    DISABLED = "disabled"


@dataclass
class AgentContext:
    """Input context passed to an agent when it executes."""
    user_id: str
    params: dict[str, Any] = field(default_factory=dict)
    # These are injected at runtime by the orchestrator
    db_session: Any = None
    llm_service: Any = None


@dataclass
class AgentResult:
    """Standardised result returned by every agent."""
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    items_processed: int = 0


class BaseAgent(ABC):
    """
    Abstract base class for all HirePilot agents.

    Each agent is a self-contained unit of work that:
      - receives an AgentContext
      - performs its task (scraping, LLM call, browser automation, etc.)
      - returns an AgentResult
    """

    name: str = "base"
    description: str = ""
    version: str = "1.0.0"
    enabled: bool = True

    # Per-agent rate limits (0 = unlimited)
    max_runs_per_hour: int = 0
    max_runs_per_day: int = 0

    def __init__(self) -> None:
        self._status = AgentStatus.IDLE
        self._last_run: datetime | None = None
        self._run_count_today: int = 0

    @property
    def status(self) -> AgentStatus:
        if not self.enabled:
            return AgentStatus.DISABLED
        return self._status

    async def run(self, context: AgentContext) -> AgentResult:
        """
        Public entry point. Wraps execute() with timing,
        logging, status tracking, and error handling.
        """
        run_id = uuid.uuid4().hex[:8]
        logger.info("Agent starting", agent=self.name, run_id=run_id, user_id=context.user_id)
        self._status = AgentStatus.RUNNING
        start = time.monotonic()

        try:
            result = await self.execute(context)
            elapsed = time.monotonic() - start
            result.duration_seconds = round(elapsed, 2)
            self._status = AgentStatus.SUCCESS if result.success else AgentStatus.FAILED
            self._last_run = datetime.now(UTC)
            self._run_count_today += 1
            logger.info(
                "Agent finished",
                agent=self.name,
                run_id=run_id,
                success=result.success,
                duration=result.duration_seconds,
                items=result.items_processed,
            )
            return result
        except Exception as exc:
            elapsed = time.monotonic() - start
            self._status = AgentStatus.FAILED
            logger.error("Agent crashed", agent=self.name, run_id=run_id, error=str(exc))
            return AgentResult(
                success=False,
                errors=[str(exc)],
                duration_seconds=round(elapsed, 2),
            )

    @abstractmethod
    async def execute(self, context: AgentContext) -> AgentResult:
        """Subclasses implement their core logic here."""
        ...

    def get_info(self) -> dict[str, Any]:
        """Return agent metadata for the dashboard."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "enabled": self.enabled,
            "status": self.status.value,
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "max_runs_per_hour": self.max_runs_per_hour,
            "max_runs_per_day": self.max_runs_per_day,
        }
