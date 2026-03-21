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

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    HAS_SELENIUM = True
except ImportError:
    HAS_SELENIUM = False

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
    LinkedIn job scraper using Selenium + Remote Chrome.

    Note: LinkedIn heavily rate-limits and may require authentication.
    In production, use LinkedIn's official Jobs API where available.
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

        if not HAS_SELENIUM:
            logger.warning("Selenium not available, skipping LinkedIn scrape")
            return jobs

        params = {
            "keywords": keywords,
            "location": filters.location or "",
            "f_TPR": "r86400",  # Past 24 hours
        }

        try:
            selenium_url = getattr(settings, "selenium_hub_url", "http://selenium-chrome:4444/wd/hub")
            chrome_options = ChromeOptions()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument(
                "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )

            def _scrape_sync() -> list[dict[str, Any]]:
                driver = webdriver.Remote(
                    command_executor=selenium_url,
                    options=chrome_options,
                )
                try:
                    url = f"{self.BASE_URL}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
                    driver.get(url)

                    # Wait for cards
                    try:
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, ".base-card"))
                        )
                    except Exception:
                        pass

                    # Scroll to load more
                    for _ in range(3):
                        driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
                        import time
                        time.sleep(random.uniform(1.5, 2.5))

                    cards = driver.find_elements(By.CSS_SELECTOR, ".base-card")
                    result: list[dict[str, Any]] = []
                    for card in cards[: filters.max_results]:
                        try:
                            title_el = card.find_elements(By.CSS_SELECTOR, ".base-search-card__title")
                            company_el = card.find_elements(By.CSS_SELECTOR, ".base-search-card__subtitle")
                            location_el = card.find_elements(By.CSS_SELECTOR, ".job-search-card__location")
                            link_el = card.find_elements(By.CSS_SELECTOR, "a.base-card__full-link")

                            title = title_el[0].text if title_el else "Unknown"
                            company = company_el[0].text if company_el else "Unknown"
                            location = location_el[0].text if location_el else None
                            link = link_el[0].get_attribute("href") if link_el else ""

                            if title and company and link:
                                result.append(self._normalize_job(
                                    title=title,
                                    company=company,
                                    location=location,
                                    description="",
                                    source_url=link,
                                    user_id=user_id,
                                ))
                        except Exception as e:
                            logger.warning("Error parsing LinkedIn job card", error=str(e))
                            continue
                    return result
                finally:
                    driver.quit()

            jobs = await asyncio.get_event_loop().run_in_executor(None, _scrape_sync)

        except Exception as e:
            logger.error("LinkedIn scraping failed", error=str(e))

        logger.info("LinkedIn scrape complete", jobs_found=len(jobs))
        return jobs


# ── Indeed Scraper ────────────────────────────────────────────────

class IndeedScraper(BaseScraper):
    """
    Indeed job scraper using httpx + BeautifulSoup.
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


# ── Company Career Page Scraper ───────────────────────────────────

CAREER_PAGE_ANALYSIS_SYSTEM = (
    "You are a web scraping expert analyzing a company career/jobs page.\n"
    "Given the HTML of a career page, identify the structure of job listings.\n\n"
    "Return ONLY valid JSON with:\n"
    '{"jobs": [{"title": "string", "location": "string or null", '
    '"url": "string (absolute URL to job detail page)", '
    '"department": "string or null", "posted_date": "string or null"}], '
    '"pagination": {"has_next": bool, "next_url": "string or null"}, '
    '"total_found": int or null}\n\n'
    "RULES:\n"
    "- Extract ALL visible job listings from the HTML\n"
    "- URLs must be absolute (prepend the base domain if relative)\n"
    "- If no jobs are found, return {\"jobs\": [], \"pagination\": {\"has_next\": false}, \"total_found\": 0}\n"
    "- Return ONLY JSON — no markdown fences, no commentary"
)

JOB_DETAIL_SYSTEM = (
    "You are a job listing parser. Extract the full job details from this HTML.\n"
    "Return ONLY valid JSON with:\n"
    '{"title": "string", "company": "string", "location": "string or null", '
    '"description": "string (full job description text)", '
    '"requirements": "string or null", "skills": ["skill1", "skill2"], '
    '"experience_required": "string or null", "salary_range": "string or null", '
    '"remote_type": "string or null", "department": "string or null"}\n'
    "Return ONLY JSON — no markdown fences, no commentary."
)


class CompanyCareerScraper(BaseScraper):
    """
    Company career page scraper using Selenium + LLM for page analysis.

    Works for any company career page by using LLM to understand the page
    structure dynamically, rather than relying on fixed CSS selectors.
    """

    source = JobSource.COMPANY_CAREER

    def __init__(
        self,
        career_url: str,
        company_name: str,
        strategy: dict | None = None,
    ):
        self.career_url = career_url
        self.company_name = company_name
        self.strategy = strategy or {}

    async def scrape(
        self, filters: JobSearchFilters, user_id: str
    ) -> list[dict[str, Any]]:
        """Scrape jobs from a company career page."""
        if not HAS_SELENIUM:
            logger.warning("Selenium not available, skipping company career scrape")
            return []

        from app.services.llm_service import LLMService
        from app.services.scraping_intelligence import ScrapingIntelligence

        llm = LLMService()
        jobs: list[dict[str, Any]] = []

        try:
            # Anti-abuse: check robots.txt first
            robots = await ScrapingIntelligence.check_robots_txt(self.career_url)
            if not robots.get("allowed", True):
                logger.warning(
                    "Career page blocked by robots.txt",
                    url=self.career_url,
                    company=self.company_name,
                )
                return []

            # Load the career page with Selenium
            html = await self._load_page_with_selenium(self.career_url)
            if not html:
                return []

            # Use LLM to analyze the page and extract job listings
            from urllib.parse import urlparse
            parsed_url = urlparse(self.career_url)
            base_domain = f"{parsed_url.scheme}://{parsed_url.netloc}"

            prompt = (
                f"Base domain: {base_domain}\n"
                f"Company: {self.company_name}\n\n"
                f"Career page HTML (first 12000 chars):\n{html[:12000]}"
            )

            try:
                analysis = await llm.generate_json(prompt, system=CAREER_PAGE_ANALYSIS_SYSTEM)
            except Exception as e:
                logger.error("LLM career page analysis failed", error=str(e))
                return []

            if not isinstance(analysis, dict):
                return []

            raw_jobs = analysis.get("jobs", [])
            logger.info(
                "Career page analysis complete",
                company=self.company_name,
                jobs_found=len(raw_jobs),
            )

            # For each job, fetch the detail page and extract full description
            for i, raw in enumerate(raw_jobs[:filters.max_results]):
                job_url = raw.get("url", "")
                if not job_url:
                    continue

                # Make URL absolute if relative
                if job_url.startswith("/"):
                    job_url = f"{base_domain}{job_url}"
                elif not job_url.startswith("http"):
                    job_url = f"{base_domain}/{job_url}"

                # Rate limiting: random delay between requests
                delay = ScrapingIntelligence.get_random_delay(2.0, 5.0)
                await asyncio.sleep(delay)

                # Fetch job detail page
                description = ""
                requirements = None
                skills_list = []
                try:
                    detail_html = await self._load_page_with_selenium(job_url)
                    if detail_html:
                        detail_prompt = (
                            f"Company: {self.company_name}\n\n"
                            f"Job detail page HTML (first 10000 chars):\n{detail_html[:10000]}"
                        )
                        detail = await llm.generate_json(detail_prompt, system=JOB_DETAIL_SYSTEM)
                        if isinstance(detail, dict):
                            description = detail.get("description", "")
                            requirements = detail.get("requirements")
                            skills_list = detail.get("skills", [])
                except Exception as e:
                    logger.warning("Failed to fetch job detail", url=job_url, error=str(e))

                title = raw.get("title", "Unknown")
                location = raw.get("location")

                jobs.append(self._normalize_job(
                    title=title,
                    company=self.company_name,
                    location=location,
                    description=description or f"{title} at {self.company_name}",
                    source_url=job_url,
                    user_id=user_id,
                    requirements=requirements,
                    technologies=json.dumps(skills_list) if skills_list else None,
                ))

        except Exception as e:
            logger.error(
                "Company career scraping failed",
                company=self.company_name,
                url=self.career_url,
                error=str(e),
            )

        logger.info(
            "Company career scrape complete",
            company=self.company_name,
            jobs_found=len(jobs),
        )
        return jobs

    async def _load_page_with_selenium(self, url: str) -> str | None:
        """Load a page with Selenium and return clean HTML."""
        from app.services.scraping_intelligence import ScrapingIntelligence

        try:
            chrome_options = ChromeOptions()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument(f"user-agent={ScrapingIntelligence.get_random_user_agent()}")

            def _load_sync() -> str:
                driver = webdriver.Remote(
                    command_executor=settings.selenium_url,
                    options=chrome_options,
                )
                try:
                    driver.get(url)
                    driver.implicitly_wait(8)

                    # Scroll to trigger lazy loading
                    for _ in range(3):
                        driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
                        import time
                        time.sleep(random.uniform(1.0, 2.0))

                    return driver.page_source
                finally:
                    driver.quit()

            html = await asyncio.get_event_loop().run_in_executor(None, _load_sync)
            return html

        except Exception as e:
            logger.error("Selenium page load failed", url=url, error=str(e))
            return None


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
        JobSource.COMPANY_CAREER: CompanyCareerScraper,
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
