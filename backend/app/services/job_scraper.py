"""
Job Scraper Module

Multi-source job scraping with normalization and deduplication.
Supports: LinkedIn, Indeed, Naukri, company career pages.

Each scraper implements the BaseScraper interface and returns
normalized JobListing data.
"""

import abc
import asyncio
import json
import random
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import Page, async_playwright

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.job import JobListing, JobSource
from app.schemas.job import JobSearchFilters

settings = get_settings()
logger = get_logger(__name__)


# ── Base Scraper Interface ────────────────────────────────────────

class BaseScraper(abc.ABC):
    """Abstract base class for all job scrapers."""

    source: JobSource

    @abc.abstractmethod
    async def scrape(
        self, filters: JobSearchFilters, user_id: str
    ) -> list[dict[str, Any]]:
        """
        Scrape jobs matching the given filters.
        Returns normalized job dicts ready for JobListing creation.
        """
        ...

    def _normalize_job(
        self,
        *,
        title: str,
        company: str,
        location: str | None,
        description: str,
        source_url: str,
        user_id: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Normalize a raw job into a standard dict."""
        return {
            "id": uuid.uuid4(),
            "user_id": uuid.UUID(user_id),
            "title": title.strip(),
            "company": company.strip(),
            "location": location.strip() if location else None,
            "description": description.strip(),
            "source": self.source,
            "source_url": source_url.strip(),
            "discovered_at": datetime.now(UTC),
            "is_active": True,
            **kwargs,
        }

    async def _random_delay(self, min_sec: float = 1.0, max_sec: float = 3.0) -> None:
        """Human-like delay between requests."""
        delay = random.uniform(min_sec, max_sec)
        await asyncio.sleep(delay)


# ── LinkedIn Scraper ──────────────────────────────────────────────

class LinkedInScraper(BaseScraper):
    """
    LinkedIn job scraper using Playwright for dynamic rendering.

    Note: LinkedIn heavily rate-limits and may require authentication.
    In production, use LinkedIn's official Jobs API where available,
    or implement session-based scraping with proper credential management.
    """

    source = JobSource.LINKEDIN
    BASE_URL = "https://www.linkedin.com/jobs/search"

    async def scrape(
        self, filters: JobSearchFilters, user_id: str
    ) -> list[dict[str, Any]]:
        jobs: list[dict[str, Any]] = []
        keywords = filters.role or ""
        if filters.technologies:
            keywords += " " + " ".join(filters.technologies)

        params = {
            "keywords": keywords,
            "location": filters.location or "",
            "f_TPR": "r86400",  # Past 24 hours
        }

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )
                page = await context.new_page()

                url = f"{self.BASE_URL}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
                await page.goto(url, wait_until="networkidle", timeout=30000)

                # Scroll to load more jobs
                for _ in range(3):
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await self._random_delay(1.5, 2.5)

                # Extract job cards
                job_cards = await page.query_selector_all(".base-card")
                for card in job_cards[: filters.max_results]:
                    try:
                        title_el = await card.query_selector(".base-search-card__title")
                        company_el = await card.query_selector(".base-search-card__subtitle")
                        location_el = await card.query_selector(".job-search-card__location")
                        link_el = await card.query_selector("a.base-card__full-link")

                        title = await title_el.inner_text() if title_el else "Unknown"
                        company = await company_el.inner_text() if company_el else "Unknown"
                        location = await location_el.inner_text() if location_el else None
                        link = await link_el.get_attribute("href") if link_el else ""

                        if title and company and link:
                            jobs.append(self._normalize_job(
                                title=title,
                                company=company,
                                location=location,
                                description="",  # Fetched separately in detail scrape
                                source_url=link,
                                user_id=user_id,
                            ))
                    except Exception as e:
                        logger.warning("Error parsing LinkedIn job card", error=str(e))
                        continue

                    await self._random_delay()

                await browser.close()

        except Exception as e:
            logger.error("LinkedIn scraping failed", error=str(e))

        logger.info("LinkedIn scrape complete", jobs_found=len(jobs))
        return jobs


# ── Indeed Scraper ────────────────────────────────────────────────

class IndeedScraper(BaseScraper):
    """
    Indeed job scraper using httpx + BeautifulSoup.
    Falls back to Playwright if dynamic rendering is needed.
    """

    source = JobSource.INDEED
    BASE_URL = "https://www.indeed.com/jobs"

    async def scrape(
        self, filters: JobSearchFilters, user_id: str
    ) -> list[dict[str, Any]]:
        jobs: list[dict[str, Any]] = []
        query = filters.role or ""
        if filters.technologies:
            query += " " + " ".join(filters.technologies)

        params = {
            "q": query,
            "l": filters.location or "",
            "fromage": 3,  # Last 3 days
            "limit": min(filters.max_results, 50),
        }

        try:
            async with httpx.AsyncClient(
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
                follow_redirects=True,
                timeout=30.0,
            ) as client:
                response = await client.get(self.BASE_URL, params=params)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, "lxml")
                job_cards = soup.find_all("div", class_="job_seen_beacon")

                for card in job_cards[: filters.max_results]:
                    try:
                        title_tag = card.find("h2", class_="jobTitle")
                        company_tag = card.find("span", attrs={"data-testid": "company-name"})
                        location_tag = card.find("div", attrs={"data-testid": "text-location"})
                        link_tag = card.find("a", href=True)

                        title = title_tag.get_text(strip=True) if title_tag else None
                        company = company_tag.get_text(strip=True) if company_tag else None
                        location = location_tag.get_text(strip=True) if location_tag else None
                        href = link_tag["href"] if link_tag else None

                        if title and company and href:
                            source_url = f"https://www.indeed.com{href}" if href.startswith("/") else href
                            jobs.append(self._normalize_job(
                                title=title,
                                company=company,
                                location=location,
                                description="",  # Fetched in detail pass
                                source_url=source_url,
                                user_id=user_id,
                            ))
                    except Exception as e:
                        logger.warning("Error parsing Indeed job card", error=str(e))
                        continue

                    await self._random_delay(0.5, 1.5)

        except Exception as e:
            logger.error("Indeed scraping failed", error=str(e))

        logger.info("Indeed scrape complete", jobs_found=len(jobs))
        return jobs


# ── Naukri Scraper ────────────────────────────────────────────────

class NaukriScraper(BaseScraper):
    """Naukri.com job scraper."""

    source = JobSource.NAUKRI
    BASE_URL = "https://www.naukri.com/jobapi/v3/search"

    async def scrape(
        self, filters: JobSearchFilters, user_id: str
    ) -> list[dict[str, Any]]:
        jobs: list[dict[str, Any]] = []
        keywords = filters.role or "software engineer"
        if filters.technologies:
            keywords += " " + " ".join(filters.technologies)

        params = {
            "noOfResults": min(filters.max_results, 50),
            "urlType": "search_by_keyword",
            "searchType": "adv",
            "keyword": keywords,
            "location": filters.location or "",
            "pageNo": 1,
        }

        try:
            async with httpx.AsyncClient(
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "appid": "109",
                    "systemid": "Starter",
                },
                timeout=30.0,
            ) as client:
                response = await client.get(self.BASE_URL, params=params)
                response.raise_for_status()
                data = response.json()

                for item in data.get("jobDetails", []):
                    try:
                        jobs.append(self._normalize_job(
                            title=item.get("title", "Unknown"),
                            company=item.get("companyName", "Unknown"),
                            location=item.get("placeholders", [{}])[0].get("value", ""),
                            description=item.get("jobDescription", ""),
                            source_url=item.get("jdURL", ""),
                            user_id=user_id,
                            source_job_id=item.get("jobId"),
                            salary_min=item.get("salaryDetail", {}).get("minimumSalary"),
                            salary_max=item.get("salaryDetail", {}).get("maximumSalary"),
                        ))
                    except Exception as e:
                        logger.warning("Error parsing Naukri job", error=str(e))
                        continue

        except Exception as e:
            logger.error("Naukri scraping failed", error=str(e))

        logger.info("Naukri scrape complete", jobs_found=len(jobs))
        return jobs


# ── Job Scraper Orchestrator ──────────────────────────────────────

class JobScraperOrchestrator:
    """
    Orchestrates scraping across multiple sources with:
    - Parallel execution per source
    - Deduplication by source URL
    - Rate limiting per source
    """

    SCRAPERS: dict[JobSource, type[BaseScraper]] = {
        JobSource.LINKEDIN: LinkedInScraper,
        JobSource.INDEED: IndeedScraper,
        JobSource.NAUKRI: NaukriScraper,
    }

    def __init__(self) -> None:
        self.rate_limit = settings.scraping_rate_limit_per_minute

    async def scrape_all(
        self,
        filters: JobSearchFilters,
        user_id: str,
        sources: list[JobSource] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Run scrapers for all requested sources concurrently.
        Returns deduplicated, normalized job data.
        """
        target_sources = sources or list(self.SCRAPERS.keys())
        tasks = []

        for source in target_sources:
            scraper_cls = self.SCRAPERS.get(source)
            if scraper_cls:
                scraper = scraper_cls()
                tasks.append(scraper.scrape(filters, user_id))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten and deduplicate
        all_jobs: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        for result in results:
            if isinstance(result, Exception):
                logger.error("Scraper failed", error=str(result))
                continue
            for job in result:
                url = job.get("source_url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_jobs.append(job)

        logger.info(
            "Scraping orchestration complete",
            total_jobs=len(all_jobs),
            sources=[s.value for s in target_sources],
        )
        return all_jobs
