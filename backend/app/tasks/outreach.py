"""
Outreach tasks.

Celery tasks for recruiter outreach automation:
connection requests, InMails, and follow-ups.
"""

import asyncio
import json
from datetime import datetime, timedelta, UTC
from typing import Any
from uuid import UUID

from app.tasks import celery_app
from app.core.database import async_session_factory
from app.core.logging import get_logger
from app.services.messaging_agent import MessageGeneratorService, MessageSenderService
from app.services.recruiter_finder import RecruiterFinderService
from app.repositories.recruiter_repo import RecruiterRepository, OutreachMessageRepository
from app.repositories.user_repo import UserRepository
from app.repositories.audit_repo import AuditLogRepository

logger = get_logger(__name__)


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    name="app.tasks.outreach.find_recruiters",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
)
def find_recruiters(
    self,
    user_id: str,
    company: str,
    role: str | None = None,
) -> dict[str, Any]:
    """
    Find recruiters at a company and save their profiles.
    """
    logger.info("Finding recruiters", user_id=user_id, company=company)

    async def _find():
        async with async_session_factory() as session:
            recruiter_repo = RecruiterRepository(session)
            user_repo = UserRepository(session)
            audit_repo = AuditLogRepository(session)

            user = await user_repo.get_by_id(UUID(user_id))
            if not user:
                return {"error": "User not found"}

            # Decrypt LinkedIn credentials
            from app.core.security import decrypt_credential
            creds = {}
            if user.encrypted_linkedin_creds:
                creds = json.loads(decrypt_credential(user.encrypted_linkedin_creds))

            finder = RecruiterFinderService()
            profiles = await finder.find_recruiters(
                company=company,
                role=role,
                user_id=user_id,
            )

            saved = 0
            for profile in profiles:
                linkedin_url = profile.get("linkedin_url", "")
                if linkedin_url:
                    existing = await recruiter_repo.get_by_linkedin_url(linkedin_url)
                    if existing:
                        continue

                from app.models.recruiter import Recruiter, ConnectionStatus
                recruiter = Recruiter(
                    user_id=UUID(user_id),
                    name=profile.get("name", ""),
                    title=profile.get("title", ""),
                    company=company,
                    linkedin_url=linkedin_url,
                    connection_status=ConnectionStatus.NOT_CONNECTED,
                )
                session.add(recruiter)
                saved += 1

            await session.commit()

            await audit_repo.log_action(
                user_id=UUID(user_id),
                action="find_recruiters",
                module="outreach",
                entity_type="recruiter",
                details=json.dumps({"company": company, "found": len(profiles), "new_saved": saved}),
            )
            await session.commit()

            return {"found": len(profiles), "new_saved": saved}

    try:
        return _run_async(_find())
    except Exception as exc:
        logger.error("Recruiter search failed", error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.outreach.send_connection_request",
    bind=True,
    max_retries=1,
)
def send_connection_request(
    self,
    user_id: str,
    recruiter_id: str,
    job_title: str | None = None,
) -> dict[str, Any]:
    """
    Generate and send a personalized LinkedIn connection request.
    """
    logger.info("Sending connection request", recruiter_id=recruiter_id)

    async def _send():
        async with async_session_factory() as session:
            recruiter_repo = RecruiterRepository(session)
            user_repo = UserRepository(session)
            audit_repo = AuditLogRepository(session)

            user = await user_repo.get_by_id(UUID(user_id))
            recruiter = await recruiter_repo.get_by_id(UUID(recruiter_id))

            if not user or not recruiter:
                return {"error": "User or recruiter not found"}

            # Generate message
            generator = MessageGeneratorService()
            message = await generator.generate_connection_request(
                recruiter_name=recruiter.name,
                recruiter_title=recruiter.title,
                company=recruiter.company,
                user_name=user.full_name,
                user_headline=getattr(user, "headline", "Software Engineer"),
                target_role=job_title,
            )

            # Send via LinkedIn
            from app.core.security import decrypt_credential
            creds = {}
            if user.encrypted_linkedin_creds:
                creds = json.loads(decrypt_credential(user.encrypted_linkedin_creds))

            sender = MessageSenderService()
            result = await sender.send_connection_request(
                profile_url=recruiter.linkedin_url,
                message=message,
                linkedin_credentials=creds,
            )

            # Record outreach
            from app.models.recruiter import OutreachMessage, OutreachStatus, ConnectionStatus
            outreach = OutreachMessage(
                user_id=UUID(user_id),
                recruiter_id=recruiter.id,
                message_type="connection_request",
                body=message,
                status=OutreachStatus.SENT if result.get("success") else OutreachStatus.FAILED,
                sent_at=datetime.now(UTC) if result.get("success") else None,
                error_message=result.get("error"),
            )
            session.add(outreach)

            # Update connection status
            if result.get("success"):
                recruiter.connection_status = ConnectionStatus.PENDING
                session.add(recruiter)

            await session.commit()

            await audit_repo.log_action(
                user_id=UUID(user_id),
                action="send_connection_request",
                module="outreach",
                entity_type="recruiter",
                entity_id=str(recruiter.id),
                details=json.dumps({"success": result.get("success", False)}),
            )
            await session.commit()

            return {
                "success": result.get("success", False),
                "message_preview": message[:100],
            }

    try:
        return _run_async(_send())
    except Exception as exc:
        logger.error("Connection request failed", error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.outreach.send_followup_message",
    bind=True,
    max_retries=1,
)
def send_followup_message(
    self,
    user_id: str,
    recruiter_id: str,
    context: str = "",
) -> dict[str, Any]:
    """
    Generate and send a follow-up message to a connected recruiter.
    """

    async def _followup():
        async with async_session_factory() as session:
            recruiter_repo = RecruiterRepository(session)
            msg_repo = OutreachMessageRepository(session)
            user_repo = UserRepository(session)

            user = await user_repo.get_by_id(UUID(user_id))
            recruiter = await recruiter_repo.get_by_id(UUID(recruiter_id))

            if not user or not recruiter:
                return {"error": "User or recruiter not found"}

            # Get previous messages for context
            previous = await msg_repo.get_messages_for_recruiter(recruiter.id)
            prev_contents = [m.body for m in previous if m.body]

            generator = MessageGeneratorService()
            message = await generator.generate_followup(
                recruiter_name=recruiter.name,
                company=recruiter.company,
                previous_messages=prev_contents,
                additional_context=context,
            )

            # Send
            from app.core.security import decrypt_credential
            creds = {}
            if user.encrypted_linkedin_creds:
                creds = json.loads(decrypt_credential(user.encrypted_linkedin_creds))

            sender = MessageSenderService()
            result = await sender.send_direct_message(
                profile_url=recruiter.linkedin_url,
                message=message,
                linkedin_credentials=creds,
            )

            from app.models.recruiter import OutreachMessage, OutreachStatus
            outreach = OutreachMessage(
                user_id=UUID(user_id),
                recruiter_id=recruiter.id,
                message_type="followup",
                body=message,
                status=OutreachStatus.SENT if result.get("success") else OutreachStatus.FAILED,
                sent_at=datetime.now(UTC) if result.get("success") else None,
            )
            session.add(outreach)
            await session.commit()

            return {
                "success": result.get("success", False),
                "message_preview": message[:100],
            }

    try:
        return _run_async(_followup())
    except Exception as exc:
        logger.error("Follow-up failed", error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(name="app.tasks.outreach.send_scheduled_followups")
def send_scheduled_followups() -> dict[str, Any]:
    """
    Send follow-ups to recruiters who haven't responded in 5+ days.
    Runs periodically via Celery Beat.
    """

    async def _scheduled():
        async with async_session_factory() as session:
            recruiter_repo = RecruiterRepository(session)
            cutoff = datetime.now(UTC) - timedelta(days=5)
            pending = await recruiter_repo.get_pending_followups(cutoff)

            triggered = 0
            for recruiter, user_id in pending:
                send_followup_message.delay(
                    user_id=str(user_id),
                    recruiter_id=str(recruiter.id),
                    context="Following up on previous outreach",
                )
                triggered += 1

            return {"followups_triggered": triggered}

    return _run_async(_scheduled())
