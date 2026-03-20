"""
Email Checker Agent

Connects to Gmail via Google API, searches for job-related emails,
classifies them via LLM, and auto-updates application statuses.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.core.logging import get_logger

logger = get_logger(__name__)

EMAIL_CLASSIFY_SYSTEM = (
    "You classify job-search emails. Given an email subject and body snippet, "
    "return JSON: {\"classification\": \"rejection|interview_invite|assessment|offer|follow_up|other\", "
    "\"company\": \"Company Name\", \"role\": \"Role if mentioned\", "
    "\"summary\": \"1-2 sentence summary\", \"next_action\": \"what the user should do\"}. "
    "Return ONLY valid JSON."
)


class EmailCheckerAgent(BaseAgent):
    name = "email_checker"
    description = "Check Gmail for job application responses and update tracking"
    max_runs_per_hour = 2
    max_runs_per_day = 24

    async def execute(self, context: AgentContext) -> AgentResult:
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.models.email_tracking import EmailTracking
        from app.repositories.user_repo import UserRepository
        from app.services.gmail_service import GmailService
        from app.services.llm_service import LLMService

        db: AsyncSession = context.db_session
        llm = context.llm_service or LLMService()

        user_repo = UserRepository(db)
        user = await user_repo.get_by_id(uuid.UUID(context.user_id))
        if not user:
            return AgentResult(success=False, errors=["User not found"])

        if not user.gmail_refresh_token:
            return AgentResult(success=False, errors=["Gmail not connected. Link your Gmail in Settings."])

        gmail = GmailService()
        try:
            emails = await gmail.search_job_emails(user.gmail_refresh_token)
        except Exception as e:
            return AgentResult(success=False, errors=[f"Gmail API error: {e}"])

        processed = 0
        for email_data in emails:
            subject = email_data.get("subject", "")
            snippet = email_data.get("snippet", "")
            from_addr = email_data.get("from", "")
            email_date = email_data.get("date")

            # Classify with LLM
            try:
                prompt = f"Subject: {subject}\nFrom: {from_addr}\nBody: {snippet[:2000]}"
                classification = await llm.generate_json(prompt, system=EMAIL_CLASSIFY_SYSTEM)
                if not isinstance(classification, dict):
                    classification = {"classification": "other", "summary": snippet[:200]}
            except Exception:
                classification = {"classification": "other", "summary": snippet[:200]}

            tracking = EmailTracking(
                id=uuid.uuid4(),
                user_id=user.id,
                email_subject=subject[:500],
                email_from=from_addr[:255],
                email_date=email_date or datetime.now(UTC),
                classification=classification.get("classification", "other"),
                summary=classification.get("summary", ""),
                company=classification.get("company"),
                role=classification.get("role"),
                next_action=classification.get("next_action"),
                raw_snippet=snippet[:2000],
                processed_at=datetime.now(UTC),
            )
            db.add(tracking)
            processed += 1

            # Auto-update application status if we can match company
            if classification.get("company"):
                await self._update_application_status(
                    db, user.id, classification
                )

        await db.commit()

        return AgentResult(
            success=True,
            data={"emails_checked": len(emails), "processed": processed},
            items_processed=processed,
        )

    @staticmethod
    async def _update_application_status(
        db: "AsyncSession",  # noqa: F821
        user_id: uuid.UUID,
        classification: dict,
    ) -> None:
        from sqlalchemy import select

        from app.models.application import Application, ApplicationStatus

        company = classification.get("company", "")
        cls = classification.get("classification", "other")

        status_map = {
            "rejection": ApplicationStatus.REJECTED,
            "interview_invite": ApplicationStatus.INTERVIEW,
            "offer": ApplicationStatus.OFFER,
        }
        new_status = status_map.get(cls)
        if not new_status:
            return

        stmt = (
            select(Application)
            .where(Application.user_id == user_id)
            .where(Application.company.ilike(f"%{company}%"))
            .where(Application.status.in_([ApplicationStatus.APPLIED, ApplicationStatus.VIEWED]))
        )
        result = await db.execute(stmt)
        apps = list(result.scalars().all())
        for app in apps:
            app.status = new_status
