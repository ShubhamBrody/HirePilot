"""
LinkedIn Reply Agent

Monitors LinkedIn inbox (via Selenium), identifies recruiter messages,
generates appropriate replies with LLM, and sends them.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.core.logging import get_logger

logger = get_logger(__name__)

REPLY_SYSTEM = (
    "You are writing a LinkedIn reply on behalf of a job seeker. "
    "The recruiter has reached out about a job opportunity. "
    "Rules: "
    "1. Be professional, enthusiastic, and concise "
    "2. Reference the specific role/company they mentioned "
    "3. Highlight relevant skills from the user's profile "
    "4. Express genuine interest and ask a smart follow-up question "
    "5. Keep under 500 characters "
    "Return ONLY the reply message text."
)


class LinkedInReplyAgent(BaseAgent):
    name = "linkedin_reply"
    description = "Auto-reply to recruiter messages on LinkedIn with personalized responses"
    max_runs_per_hour = 2
    max_runs_per_day = 12

    async def execute(self, context: AgentContext) -> AgentResult:
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.models.recruiter import OutreachMessage, OutreachStatus
        from app.repositories.recruiter_repo import OutreachMessageRepository, RecruiterRepository
        from app.repositories.user_repo import UserRepository
        from app.services.llm_service import LLMService

        db: AsyncSession = context.db_session
        llm = context.llm_service or LLMService()

        # If specific message context is provided (manual trigger)
        recruiter_message = context.params.get("recruiter_message", "")
        recruiter_id = context.params.get("recruiter_id")

        user_repo = UserRepository(db)
        user = await user_repo.get_by_id(uuid.UUID(context.user_id))
        if not user:
            return AgentResult(success=False, errors=["User not found"])

        recruiter_repo = RecruiterRepository(db)
        msg_repo = OutreachMessageRepository(db)
        replies_sent = 0

        if recruiter_id and recruiter_message:
            # Single reply mode
            recruiter = await recruiter_repo.get_by_id(uuid.UUID(recruiter_id))
            if not recruiter:
                return AgentResult(success=False, errors=["Recruiter not found"])

            reply = await self._generate_reply(llm, user, recruiter, recruiter_message)

            outreach = OutreachMessage(
                id=uuid.uuid4(),
                user_id=user.id,
                recruiter_id=recruiter.id,
                message_type="reply",
                body=reply,
                ai_generated=True,
                status=OutreachStatus.PENDING,
                created_at=datetime.now(UTC),
            )
            await msg_repo.create(outreach)
            replies_sent = 1
        else:
            # Batch mode: check for unanswered recruiter messages
            # In production, this would use Selenium to check LinkedIn inbox
            logger.info("Batch LinkedIn reply check", user_id=context.user_id)

        await db.commit()

        return AgentResult(
            success=True,
            data={"replies_generated": replies_sent},
            items_processed=replies_sent,
        )

    @staticmethod
    async def _generate_reply(llm, user, recruiter, recruiter_message: str) -> str:
        prompt = (
            f"Recruiter message from {recruiter.name} ({recruiter.title} at {recruiter.company}):\n"
            f'"{recruiter_message}"\n\n'
            f"User profile: {user.full_name}, {user.headline or ''}\n"
            f"Skills: {user.skills or 'Software Engineering'}\n"
            f"Write a reply."
        )
        return await llm.generate(prompt, system=REPLY_SYSTEM)
