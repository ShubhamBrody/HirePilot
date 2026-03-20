"""
LinkedIn Message Agent

Generates and sends personalized LinkedIn messages:
connection requests, follow-ups, and InMail.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.core.logging import get_logger

logger = get_logger(__name__)

MESSAGE_SYSTEM = (
    "You write professional LinkedIn outreach messages. Rules: "
    "1. Be warm, genuine, and specific to the person "
    "2. Reference their role/company/work "
    "3. Keep connection requests under 300 characters "
    "4. Never use generic templates "
    "5. Show you've done research "
    "Return ONLY the message text, no subject line for connection requests."
)


class LinkedInMessageAgent(BaseAgent):
    name = "linkedin_message"
    description = "Generate and send personalized LinkedIn outreach messages"
    max_runs_per_hour = 10
    max_runs_per_day = 50

    async def execute(self, context: AgentContext) -> AgentResult:
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.models.recruiter import OutreachMessage, OutreachStatus
        from app.repositories.recruiter_repo import OutreachMessageRepository, RecruiterRepository
        from app.repositories.user_repo import UserRepository
        from app.services.llm_service import LLMService

        db: AsyncSession = context.db_session
        llm = context.llm_service or LLMService()

        recruiter_id = context.params.get("recruiter_id")
        message_type = context.params.get("message_type", "connection_request")
        custom_message = context.params.get("custom_message")

        if not recruiter_id:
            return AgentResult(success=False, errors=["recruiter_id is required"])

        user_repo = UserRepository(db)
        recruiter_repo = RecruiterRepository(db)

        user = await user_repo.get_by_id(uuid.UUID(context.user_id))
        recruiter = await recruiter_repo.get_by_id(uuid.UUID(recruiter_id))

        if not user or not recruiter:
            return AgentResult(success=False, errors=["User or recruiter not found"])

        # Generate message via LLM if not custom
        if custom_message:
            body = custom_message
        else:
            prompt = (
                f"Write a {message_type.replace('_', ' ')} for LinkedIn.\n"
                f"From: {user.full_name}, {user.headline or ''}\n"
                f"To: {recruiter.name}, {recruiter.title or ''} at {recruiter.company}\n"
                f"User skills: {user.skills or 'Software Engineering'}\n"
            )
            if message_type == "connection_request":
                prompt += "Keep under 300 characters."
            body = await llm.generate(prompt, system=MESSAGE_SYSTEM)

        # Store the outreach message
        msg_repo = OutreachMessageRepository(db)
        outreach = OutreachMessage(
            id=uuid.uuid4(),
            user_id=user.id,
            recruiter_id=recruiter.id,
            message_type=message_type,
            body=body.strip(),
            ai_generated=custom_message is None,
            status=OutreachStatus.PENDING,
            created_at=datetime.now(UTC),
        )
        await msg_repo.create(outreach)
        await db.commit()

        return AgentResult(
            success=True,
            data={
                "message_id": str(outreach.id),
                "body": body.strip(),
                "recruiter": recruiter.name,
                "type": message_type,
            },
            items_processed=1,
        )
