"""
Agent Celery Tasks

Generic task to run any agent asynchronously, plus periodic
scheduled tasks for continuous agents (job search, email check, etc.).
"""

import asyncio
import json
import uuid
from datetime import UTC, datetime

from app.tasks import celery_app
from app.core.logging import get_logger

logger = get_logger(__name__)


def _run_async(coro):
    """Run an async coroutine in a synchronous Celery task."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


async def _execute_agent(agent_name: str, user_id: str, params: dict) -> dict:
    """Core async function that sets up DB, LLM, and runs an agent."""
    from app.agents.base import AgentContext
    from app.agents.orchestrator import get_orchestrator
    from app.core.database import async_session_factory
    from app.models.agent_execution import AgentExecution
    from app.services.llm_service import LLMService

    orch = get_orchestrator()

    async with async_session_factory() as db:
        # Record execution
        execution = AgentExecution(
            id=uuid.uuid4(),
            user_id=uuid.UUID(user_id),
            agent_name=agent_name,
            status="running",
            params=json.dumps(params),
            started_at=datetime.now(UTC),
        )
        db.add(execution)
        await db.commit()

        context = AgentContext(
            user_id=user_id,
            params=params,
            db_session=db,
            llm_service=LLMService(),
        )
        result = await orch.dispatch(agent_name, context)

        # Update execution
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
            "execution_id": str(execution.id),
        }


@celery_app.task(name="app.tasks.agent_tasks.run_agent", bind=True, max_retries=1)
def run_agent(self, agent_name: str, user_id: str, params: dict | None = None):
    """Generic task to run any agent asynchronously via Celery."""
    logger.info("Celery agent task starting", agent=agent_name, user_id=user_id)
    try:
        return _run_async(_execute_agent(agent_name, user_id, params or {}))
    except Exception as exc:
        logger.error("Celery agent task failed", agent=agent_name, error=str(exc))
        raise self.retry(exc=exc) from exc


@celery_app.task(name="app.tasks.agent_tasks.run_job_search_periodic")
def run_job_search_periodic():
    """Periodic: search jobs for all active users with preferences."""
    logger.info("Periodic job search starting")

    async def _run():
        from app.core.database import async_session_factory
        from app.repositories.user_repo import UserRepository

        async with async_session_factory() as db:
            repo = UserRepository(db)
            users = await repo.get_active_users_with_preferences()
            for user in users:
                run_agent.delay("job_search", str(user.id), {})
            return len(users)

    count = _run_async(_run())
    logger.info("Periodic job search dispatched", users=count)


@celery_app.task(name="app.tasks.agent_tasks.run_email_check_periodic")
def run_email_check_periodic():
    """Periodic: check Gmail for all users with connected accounts."""
    logger.info("Periodic email check starting")

    async def _run():
        from sqlalchemy import select

        from app.core.database import async_session_factory
        from app.models.user import User

        async with async_session_factory() as db:
            stmt = select(User).where(
                User.is_active.is_(True),
                User.gmail_refresh_token.isnot(None),
            )
            result = await db.execute(stmt)
            users = list(result.scalars().all())
            for user in users:
                run_agent.delay("email_checker", str(user.id), {})
            return len(users)

    count = _run_async(_run())
    logger.info("Periodic email check dispatched", users=count)


@celery_app.task(name="app.tasks.agent_tasks.run_linkedin_reply_periodic")
def run_linkedin_reply_periodic():
    """Periodic: check LinkedIn inbox for recruiter messages."""
    logger.info("Periodic LinkedIn reply check starting")

    async def _run():
        from app.core.database import async_session_factory
        from app.repositories.user_repo import UserRepository

        async with async_session_factory() as db:
            repo = UserRepository(db)
            users = await repo.get_active_users_with_preferences()
            for user in users:
                if user.encrypted_linkedin_creds:
                    run_agent.delay("linkedin_reply", str(user.id), {})
            return len(users)

    count = _run_async(_run())
    logger.info("Periodic LinkedIn reply dispatched", users=count)


@celery_app.task(name="app.tasks.agent_tasks.run_company_search_periodic")
def run_company_search_periodic():
    """Periodic: scrape company career pages for users with company_search_enabled."""
    logger.info("Periodic company career search starting")

    async def _run():
        from sqlalchemy import select

        from app.core.database import async_session_factory
        from app.models.user import User

        async with async_session_factory() as db:
            stmt = select(User).where(
                User.is_active.is_(True),
                User.company_search_enabled.is_(True),
            )
            result = await db.execute(stmt)
            users = list(result.scalars().all())
            for user in users:
                run_agent.delay("company_search", str(user.id), {})
            return len(users)

    count = _run_async(_run())
    logger.info("Periodic company career search dispatched", users=count)
