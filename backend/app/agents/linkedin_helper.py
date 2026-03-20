"""
LinkedIn Helper for Agents

Shared utility that agents use to get LinkedIn credentials
and auto-connect before performing LinkedIn operations.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from app.core.logging import get_logger
from app.core.security import decrypt_credential

logger = get_logger(__name__)


async def get_linkedin_credentials(db_session: Any, user_id: str) -> dict[str, str] | None:
    """
    Load and decrypt LinkedIn credentials for a user.
    Returns {"username": ..., "password": ...} or None if not configured.
    """
    from app.repositories.user_repo import UserRepository

    repo = UserRepository(db_session)
    user = await repo.get_by_id(uuid.UUID(user_id))
    if not user or not user.encrypted_linkedin_creds:
        return None

    try:
        creds = json.loads(decrypt_credential(user.encrypted_linkedin_creds))
        username = creds.get("username", "")
        password = creds.get("password", "")
        if username and password:
            return {"username": username, "password": password}
        return None
    except Exception as e:
        logger.warning("Failed to decrypt LinkedIn credentials", error=str(e))
        return None


async def linkedin_search_jobs(
    db_session: Any,
    user_id: str,
    keywords: str,
    location: str = "",
    max_results: int = 25,
) -> dict[str, Any]:
    """
    Search LinkedIn for jobs, auto-connecting with saved credentials.
    Returns results dict from LinkedInService.search_jobs().
    """
    creds = await get_linkedin_credentials(db_session, user_id)
    if not creds:
        return {
            "success": False,
            "error": "LinkedIn credentials not configured. Add them in Settings.",
            "jobs": [],
        }

    from app.services.linkedin_service import LinkedInService

    svc = LinkedInService()
    result = await asyncio.get_event_loop().run_in_executor(
        None, svc.search_jobs, creds["username"], creds["password"], keywords, location, max_results
    )
    return result


async def linkedin_search_people(
    db_session: Any,
    user_id: str,
    company: str,
    role_keywords: str = "recruiter OR hiring manager",
    max_results: int = 10,
) -> dict[str, Any]:
    """
    Search LinkedIn for people (recruiters) at a company.
    Auto-connects with saved credentials.
    """
    creds = await get_linkedin_credentials(db_session, user_id)
    if not creds:
        return {
            "success": False,
            "error": "LinkedIn credentials not configured. Add them in Settings.",
            "people": [],
        }

    from app.services.linkedin_service import LinkedInService

    svc = LinkedInService()
    result = await asyncio.get_event_loop().run_in_executor(
        None, svc.search_people, creds["username"], creds["password"], company, role_keywords, max_results
    )
    return result


async def linkedin_fetch_messages(
    db_session: Any,
    user_id: str,
    count: int = 10,
) -> dict[str, Any]:
    """
    Fetch recent LinkedIn messages. Auto-connects with saved credentials.
    """
    creds = await get_linkedin_credentials(db_session, user_id)
    if not creds:
        return {
            "success": False,
            "error": "LinkedIn credentials not configured. Add them in Settings.",
            "conversations": [],
        }

    from app.services.linkedin_service import LinkedInService

    svc = LinkedInService()
    result = await asyncio.get_event_loop().run_in_executor(
        None, svc.fetch_recent_messages, creds["username"], creds["password"], count
    )
    return result
