"""
Salary Negotiator Agent

Chat-based agent that provides salary negotiation advice,
counter-offer suggestions, and benefit analysis.
"""

from __future__ import annotations

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.core.logging import get_logger

logger = get_logger(__name__)

NEGOTIATOR_SYSTEM = (
    "You are an expert salary negotiation coach with deep knowledge of tech compensation. "
    "Help the user negotiate their offer confidently. Provide: "
    "1. Data-driven counter-offer suggestions "
    "2. Specific talking points and scripts "
    "3. Analysis of total compensation (base, RSU, bonus, benefits) "
    "4. Risk assessment of negotiating "
    "5. Alternative negotiation levers (signing bonus, remote, PTO, etc.) "
    "Be supportive but realistic. Use concrete numbers when possible."
)


class SalaryNegotiatorAgent(BaseAgent):
    name = "salary_negotiator"
    description = "Get AI-powered salary negotiation advice and counter-offer scripts"
    max_runs_per_hour = 20
    max_runs_per_day = 100

    async def execute(self, context: AgentContext) -> AgentResult:
        from app.services.llm_service import LLMService

        llm = context.llm_service or LLMService()

        user_message = context.params.get("message", "")
        conversation_history = context.params.get("history", [])

        if not user_message:
            return AgentResult(success=False, errors=["No message provided"])

        # Build chat messages
        messages = [{"role": "system", "content": NEGOTIATOR_SYSTEM}]
        for msg in conversation_history:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
        messages.append({"role": "user", "content": user_message})

        try:
            response = await llm.chat(messages)
        except Exception as e:
            return AgentResult(success=False, errors=[f"LLM error: {e}"])

        return AgentResult(
            success=True,
            data={"response": response, "role": "assistant"},
            items_processed=1,
        )
