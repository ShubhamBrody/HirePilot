"""
Career Page Discovery Service

Uses GitHub AI Models (with internet access) to discover company career page URLs.
Validates URLs are reachable before storing.
"""

import httpx

from app.core.logging import get_logger
from app.services.llm_service import LLMService

logger = get_logger(__name__)

DISCOVERY_SYSTEM_PROMPT = (
    "You are a career-page URL discovery assistant with internet search capability.\n"
    "Given a company name, find the URL of their official careers/jobs page.\n\n"
    "RULES:\n"
    "- Return the MAIN careers page (e.g. careers.google.com, not a specific job listing)\n"
    "- Prefer the root careers domain or /careers path on the company's main site\n"
    "- For companies using ATS platforms (Workday, Greenhouse, Lever, etc.), return the ATS careers URL\n"
    "- If the company has multiple career portals (regional), prefer the global/US one\n"
    "- Include 1-3 alternate URLs if available (e.g. regional portals, different ATS pages)\n"
    "- Confidence should reflect how certain you are: 0.9+ for well-known companies, "
    "0.5-0.8 for less known ones, <0.5 if uncertain\n\n"
    'Return ONLY valid JSON: {"career_url": "string or null", "confidence": float 0.0-1.0, '
    '"alternate_urls": ["url1", "url2"], "notes": "brief explanation"}\n'
    "Return ONLY JSON — no markdown fences, no commentary."
)


class CareerPageDiscoveryService:
    """Discovers company career page URLs using LLM with internet access."""

    def __init__(self, llm: LLMService | None = None):
        self.llm = llm or LLMService()

    async def discover_career_url(self, company_name: str) -> dict:
        """
        Use GitHub AI Models to find a company's career page URL.

        Returns: {career_url, confidence, alternate_urls, error}
        """
        prompt = (
            f"Find the official careers/jobs page URL for the company: {company_name}\n\n"
            f"Search for: \"{company_name} careers page\" or \"{company_name} jobs portal\"\n"
            f"Return the structured JSON result."
        )

        try:
            result = await self.llm.generate_json(prompt, system=DISCOVERY_SYSTEM_PROMPT)
            if not isinstance(result, dict):
                return {"career_url": None, "confidence": 0.0, "alternate_urls": [], "error": "Invalid LLM response"}

            career_url = result.get("career_url")
            confidence = float(result.get("confidence", 0.0))
            alternate_urls = result.get("alternate_urls", [])

            # Validate the primary URL is reachable
            if career_url:
                is_reachable = await self._validate_url(career_url)
                if not is_reachable:
                    logger.warning("Discovered career URL not reachable", url=career_url, company=company_name)
                    # Try alternates
                    for alt_url in alternate_urls:
                        if await self._validate_url(alt_url):
                            career_url = alt_url
                            confidence = max(0.5, confidence - 0.2)
                            break
                    else:
                        confidence = max(0.2, confidence - 0.3)

            return {
                "career_url": career_url,
                "confidence": confidence,
                "alternate_urls": [u for u in alternate_urls if u != career_url],
                "error": None,
            }

        except Exception as e:
            logger.error("Career URL discovery failed", company=company_name, error=str(e))
            return {"career_url": None, "confidence": 0.0, "alternate_urls": [], "error": str(e)}

    async def _validate_url(self, url: str) -> bool:
        """Check if a URL is reachable via HEAD request."""
        try:
            async with httpx.AsyncClient(
                timeout=15.0,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            ) as client:
                resp = await client.head(url)
                return resp.status_code < 400
        except Exception:
            # Try GET as fallback (some servers reject HEAD)
            try:
                async with httpx.AsyncClient(
                    timeout=15.0,
                    follow_redirects=True,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                ) as client:
                    resp = await client.get(url)
                    return resp.status_code < 400
            except Exception:
                return False
