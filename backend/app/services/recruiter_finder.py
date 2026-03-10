"""
Recruiter Finder Service

Discovers recruiters and hiring managers using an Ollama LLM
to generate realistic recruiter profiles for a given company & role.
Falls back to deterministic suggestions when Ollama is unavailable.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.recruiter import ConnectionStatus
from app.services.llm_service import LLMService

settings = get_settings()
logger = get_logger(__name__)


_SYSTEM_PROMPT = (
    "You are an expert recruiter research assistant. "
    "Given a company name and a target role, generate a JSON array of realistic "
    "recruiter / hiring-manager profiles that a job seeker might want to connect with. "
    "Each object MUST have exactly these keys: "
    '"name" (string), "title" (string, e.g. "Senior Technical Recruiter"), '
    '"company" (string), "linkedin_url" (string — use the pattern '
    '"https://www.linkedin.com/in/<firstname>-<lastname>-<random6digits>"), '
    '"email" (string or null). '
    "Return ONLY valid JSON — no markdown, no commentary."
)


def _build_prompt(company: str, role: str, count: int) -> str:
    role_part = f" for the role **{role}**" if role else ""
    return (
        f"Find {count} recruiters and hiring managers at **{company}**{role_part}.\n"
        f"Return a JSON array of {count} objects."
    )


class RecruiterFinderService:
    """
    Discovers recruiters related to job postings.

    Primary strategy: ask an Ollama LLM to generate plausible recruiter
    profiles (name, title, LinkedIn URL, email) for the target company.
    Falls back to a small set of deterministic suggestions if the LLM
    is unreachable.
    """

    def __init__(self) -> None:
        self.llm = LLMService()

    async def find_recruiters(
        self,
        company: str,
        role: str,
        user_id: str,
        *,
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Find recruiters related to a company and role.
        Returns normalized recruiter dicts ready for DB insertion.
        """
        raw_profiles = await self._discover_via_llm(company, role or "Software Engineer", max_results)

        if not raw_profiles:
            logger.warning("LLM returned no results, using fallback")
            raw_profiles = self._fallback_profiles(company, role or "Software Engineer")

        # Normalize into DB-ready dicts
        recruiters: list[dict[str, Any]] = []
        for p in raw_profiles[:max_results]:
            recruiters.append({
                "id": uuid.uuid4(),
                "user_id": uuid.UUID(user_id),
                "name": p.get("name", "Unknown"),
                "title": p.get("title"),
                "company": p.get("company", company),
                "email": p.get("email"),
                "linkedin_url": p.get("linkedin_url"),
                "connection_status": ConnectionStatus.NOT_CONNECTED,
                "platform": "linkedin",
                "discovered_at": datetime.now(UTC),
            })

        logger.info(
            "Recruiter discovery complete",
            company=company,
            role=role,
            found=len(recruiters),
        )
        return recruiters

    # ── LLM-backed discovery ─────────────────────────────────────

    async def _discover_via_llm(
        self, company: str, role: str, count: int
    ) -> list[dict[str, Any]]:
        """Call Ollama to generate recruiter profiles."""
        try:
            if not await self.llm.is_available():
                logger.warning("Ollama is not reachable, skipping LLM discovery")
                return []

            prompt = _build_prompt(company, role, count)
            profiles = await self.llm.generate_json(prompt, system=_SYSTEM_PROMPT)

            if isinstance(profiles, list):
                return profiles
            logger.warning("LLM returned non-list JSON", type=type(profiles).__name__)
            return []

        except Exception as e:
            logger.error("LLM recruiter discovery failed", error=str(e))
            return []

    # ── Deterministic fallback ───────────────────────────────────

    @staticmethod
    def _fallback_profiles(company: str, role: str) -> list[dict[str, Any]]:
        """Return generic recruiter suggestions when LLM is unavailable."""
        slug = company.lower().replace(" ", "-").replace(".", "")
        titles = [
            "Senior Technical Recruiter",
            "Talent Acquisition Partner",
            "Engineering Hiring Manager",
            f"Head of {role} Recruiting",
            "University & Early Career Recruiter",
        ]
        names = [
            "Alex Johnson",
            "Priya Sharma",
            "Michael Chen",
            "Sarah Williams",
            "David Kim",
        ]
        results = []
        for name, title in zip(names, titles):
            first, last = name.lower().split()
            results.append({
                "name": name,
                "title": f"{title} at {company}",
                "company": company,
                "linkedin_url": f"https://www.linkedin.com/in/{first}-{last}-{slug}",
                "email": None,
            })
        return results
