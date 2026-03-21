"""
Scraping Intelligence Service

Adaptive scraping strategy management:
- Track successful CSS selectors/page structures per company
- Classify errors and adjust strategy
- Enforce anti-abuse measures (robots.txt, delays, backoff)
"""

import json
import random
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

# Default User-Agent pool for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


class ScrapingIntelligence:
    """Manages adaptive scraping strategies per company."""

    @staticmethod
    def get_random_user_agent() -> str:
        return random.choice(USER_AGENTS)

    @staticmethod
    def get_random_delay(min_sec: float = 2.0, max_sec: float = 5.0) -> float:
        """Return a random delay to be human-like."""
        return random.uniform(min_sec, max_sec)

    @staticmethod
    def classify_error(error: Exception, status_code: int | None = None) -> str:
        """Classify a scraping error into a category for learning."""
        from app.models.scraping_log import ScrapingErrorType

        error_str = str(error).lower()

        if status_code == 403:
            return ScrapingErrorType.BLOCKED.value
        if status_code == 429:
            return ScrapingErrorType.BLOCKED.value
        if status_code == 401:
            return ScrapingErrorType.AUTH_REQUIRED.value
        if "timeout" in error_str or "timed out" in error_str:
            return ScrapingErrorType.TIMEOUT.value
        if "captcha" in error_str or "challenge" in error_str:
            return ScrapingErrorType.CAPTCHA.value
        if "connection" in error_str or "dns" in error_str:
            return ScrapingErrorType.NETWORK.value
        if "element" in error_str or "selector" in error_str:
            return ScrapingErrorType.STRUCTURE_CHANGE.value
        return ScrapingErrorType.OTHER.value

    @staticmethod
    def should_backoff(recent_failures: int) -> tuple[bool, int]:
        """
        Determine if we should back off based on recent failures.
        Returns (should_skip, wait_hours).
        """
        if recent_failures >= 5:
            return True, 48  # Stop for 2 days
        if recent_failures >= 3:
            return True, 24  # Stop for 1 day
        if recent_failures >= 2:
            return True, 6   # Wait 6 hours
        return False, 0

    @staticmethod
    def parse_strategy(strategy_json: str | None) -> dict[str, Any]:
        """Parse a stored scraping strategy JSON string."""
        if not strategy_json:
            return {}
        try:
            return json.loads(strategy_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    @staticmethod
    def build_strategy(
        *,
        job_list_selector: str | None = None,
        job_card_selector: str | None = None,
        title_selector: str | None = None,
        link_selector: str | None = None,
        location_selector: str | None = None,
        pagination_selector: str | None = None,
        has_infinite_scroll: bool = False,
        needs_search_query: bool = False,
        search_input_selector: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> str:
        """Build a strategy JSON from discovered page structure."""
        strategy = {
            "job_list_selector": job_list_selector,
            "job_card_selector": job_card_selector,
            "title_selector": title_selector,
            "link_selector": link_selector,
            "location_selector": location_selector,
            "pagination_selector": pagination_selector,
            "has_infinite_scroll": has_infinite_scroll,
            "needs_search_query": needs_search_query,
            "search_input_selector": search_input_selector,
            "discovered_at": datetime.now(UTC).isoformat(),
        }
        if extra:
            strategy.update(extra)
        return json.dumps({k: v for k, v in strategy.items() if v is not None})

    @staticmethod
    async def check_robots_txt(base_url: str) -> dict[str, Any]:
        """
        Check robots.txt for the given domain.
        Returns info about crawling permissions.
        """
        from urllib.parse import urlparse

        parsed = urlparse(base_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(robots_url)
                if resp.status_code != 200:
                    return {"allowed": True, "robots_found": False}

                content = resp.text.lower()
                # Basic check: look for disallow rules for career/job paths
                lines = content.split("\n")
                disallowed_paths = []
                current_agent = ""
                for line in lines:
                    line = line.strip()
                    if line.startswith("user-agent:"):
                        current_agent = line.split(":", 1)[1].strip()
                    elif line.startswith("disallow:") and current_agent in ("*", ""):
                        path = line.split(":", 1)[1].strip()
                        if path:
                            disallowed_paths.append(path)

                # Check if careers/jobs paths are disallowed
                careers_blocked = any(
                    keyword in path
                    for path in disallowed_paths
                    for keyword in ("/careers", "/jobs", "/career", "/job")
                )

                return {
                    "allowed": not careers_blocked,
                    "robots_found": True,
                    "disallowed_paths": disallowed_paths[:20],
                    "careers_blocked": careers_blocked,
                }
        except Exception:
            return {"allowed": True, "robots_found": False}
