"""
HirePilot AI Agent System

Registry of all specialized agents coordinated by the AgentOrchestrator.
"""

from app.agents.base import AgentContext, AgentResult, BaseAgent

__all__ = ["BaseAgent", "AgentContext", "AgentResult"]
