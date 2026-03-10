"""
Recruiter Finder Service

Discovers recruiters and hiring managers from LinkedIn
and other platforms based on job posting context.
"""

import asyncio
import random
import uuid
from datetime import UTC, datetime
from typing import Any

from playwright.async_api import async_playwright

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.recruiter import ConnectionStatus, Recruiter

settings = get_settings()
logger = get_logger(__name__)


class RecruiterFinderService:
    """
    Discovers recruiters related to job postings.

    Strategies:
    1. Search LinkedIn for recruiters at the hiring company
    2. Parse job posting pages for recruiter info
    3. Search with queries like "Hiring SDE 2 at <Company>"
    """

    SEARCH_QUERIES = [
        "Hiring {role} at {company}",
        "Tech recruiter {company}",
        "{role} hiring {company}",
        "Talent acquisition {company}",
        "Engineering hiring manager {company}",
    ]

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
        Returns normalized recruiter dicts.
        """
        recruiters: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        queries = [
            q.format(role=role, company=company) for q in self.SEARCH_QUERIES[:3]
        ]

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )
                page = await context.new_page()

                for query in queries:
                    if len(recruiters) >= max_results:
                        break

                    try:
                        # Search LinkedIn people
                        search_url = (
                            f"https://www.linkedin.com/search/results/people/"
                            f"?keywords={query}&origin=GLOBAL_SEARCH_HEADER"
                        )
                        await page.goto(search_url, wait_until="networkidle", timeout=30000)
                        await asyncio.sleep(random.uniform(2.0, 4.0))

                        # Extract profile cards
                        cards = await page.query_selector_all(".reusable-search__result-container")

                        for card in cards:
                            try:
                                name_el = await card.query_selector(
                                    ".entity-result__title-text a span[aria-hidden='true']"
                                )
                                title_el = await card.query_selector(
                                    ".entity-result__primary-subtitle"
                                )
                                link_el = await card.query_selector(
                                    ".entity-result__title-text a"
                                )

                                name = await name_el.inner_text() if name_el else None
                                title = await title_el.inner_text() if title_el else None
                                link = await link_el.get_attribute("href") if link_el else None

                                if name and link and link not in seen_urls:
                                    seen_urls.add(link)
                                    recruiters.append({
                                        "id": uuid.uuid4(),
                                        "user_id": uuid.UUID(user_id),
                                        "name": name.strip(),
                                        "title": title.strip() if title else None,
                                        "company": company,
                                        "linkedin_url": link.split("?")[0],
                                        "connection_status": ConnectionStatus.NOT_CONNECTED,
                                        "platform": "linkedin",
                                        "discovered_at": datetime.now(UTC),
                                    })
                            except Exception as e:
                                logger.warning("Error parsing recruiter card", error=str(e))
                                continue

                        await asyncio.sleep(random.uniform(3.0, 6.0))

                    except Exception as e:
                        logger.warning("Recruiter search query failed", query=query, error=str(e))
                        continue

                await browser.close()

        except Exception as e:
            logger.error("Recruiter finder failed", error=str(e))

        logger.info(
            "Recruiter discovery complete",
            company=company,
            role=role,
            found=len(recruiters),
        )
        return recruiters[:max_results]

    async def check_connection_status(
        self, page: Any, linkedin_url: str
    ) -> ConnectionStatus:
        """
        Check if the user is already connected with a recruiter on LinkedIn.
        Requires an authenticated LinkedIn session.
        """
        try:
            await page.goto(linkedin_url, wait_until="networkidle", timeout=20000)
            await asyncio.sleep(random.uniform(1.0, 2.0))

            # Look for connection indicators
            connect_btn = await page.query_selector("button[aria-label*='Connect']")
            message_btn = await page.query_selector("button[aria-label*='Message']")
            pending_btn = await page.query_selector("button[aria-label*='Pending']")

            if message_btn:
                return ConnectionStatus.CONNECTED
            elif pending_btn:
                return ConnectionStatus.PENDING
            elif connect_btn:
                return ConnectionStatus.NOT_CONNECTED
            else:
                return ConnectionStatus.NOT_CONNECTED

        except Exception as e:
            logger.warning("Connection status check failed", url=linkedin_url, error=str(e))
            return ConnectionStatus.NOT_CONNECTED
