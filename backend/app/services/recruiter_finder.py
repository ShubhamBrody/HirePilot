"""
Recruiter Finder Service

Legacy module — previously generated fake LLM recruiter profiles.
Now returns empty results; real recruiter discovery is handled by
LinkedIn people search in the /find endpoint and RecruiterSearchAgent.
"""

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


class RecruiterFinderService:
    """
    Legacy recruiter finder — returns empty results.

    Real recruiter discovery is handled by LinkedIn people search
    in the /find endpoint and RecruiterSearchAgent.
    """

    async def find_recruiters(
        self,
        company: str,
        role: str,
        user_id: str,
        *,
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Legacy entry point — returns empty list.

        Real recruiter discovery uses LinkedIn people search.
        """
        logger.info(
            "RecruiterFinderService.find_recruiters called (legacy, returning empty)",
            company=company,
            role=role,
        )
        return []
