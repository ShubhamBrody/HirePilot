"""
LinkedIn Service

Uses Selenium Remote WebDriver to interact with LinkedIn:
- Log in with stored credentials (with cookie persistence)
- Wait for user to solve security challenges via noVNC (port 7900)
- Check connectivity / validate credentials
- Fetch recent inbox messages (conversations)
"""

import json
import os
import time
from pathlib import Path
from typing import Any

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

# Cookie storage directory (Docker volume mounted at /data/linkedin_cookies)
COOKIE_DIR = Path("/data/linkedin_cookies")
COOKIE_DIR.mkdir(parents=True, exist_ok=True)

# How long to wait for user to solve a security challenge via VNC
CHALLENGE_TIMEOUT = 120  # seconds


class LinkedInService:
    """Selenium-based LinkedIn interaction service."""

    LOGIN_URL = "https://www.linkedin.com/login"
    MESSAGING_URL = "https://www.linkedin.com/messaging/"
    FEED_URL = "https://www.linkedin.com/feed/"

    def __init__(self) -> None:
        self._selenium_url = settings.selenium_url

    def _create_driver(self) -> webdriver.Remote:
        chrome_options = ChromeOptions()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        return webdriver.Remote(
            command_executor=self._selenium_url,
            options=chrome_options,
        )

    def _cookie_path(self, username: str) -> Path:
        """Per-user cookie file path."""
        safe_name = username.replace("@", "_at_").replace(".", "_")
        return COOKIE_DIR / f"{safe_name}.json"

    def _save_cookies(self, driver: webdriver.Remote, username: str) -> None:
        """Persist browser cookies to disk for reuse."""
        try:
            cookies = driver.get_cookies()
            self._cookie_path(username).write_text(json.dumps(cookies))
            logger.info("LinkedIn cookies saved", user=username)
        except Exception as e:
            logger.warning("Failed to save LinkedIn cookies", error=str(e))

    def _load_cookies(self, driver: webdriver.Remote, username: str) -> bool:
        """Load saved cookies into the driver. Returns True if cookies existed."""
        path = self._cookie_path(username)
        if not path.exists():
            return False
        try:
            cookies = json.loads(path.read_text())
            driver.get("https://www.linkedin.com")
            time.sleep(2)
            for cookie in cookies:
                # Remote driver may reject some cookie fields
                cookie.pop("sameSite", None)
                cookie.pop("storeId", None)
                try:
                    driver.add_cookie(cookie)
                except Exception:
                    continue
            logger.info("LinkedIn cookies loaded", user=username)
            return True
        except Exception as e:
            logger.warning("Failed to load LinkedIn cookies", error=str(e))
            return False

    def _is_logged_in(self, driver: webdriver.Remote) -> bool:
        """Check if the current page indicates a logged-in LinkedIn session."""
        url = driver.current_url
        if any(x in url for x in ["/feed", "/messaging", "/mynetwork", "/jobs", "/in/"]):
            return True
        try:
            page_src = driver.page_source.lower()
            return "global-nav" in page_src
        except Exception:
            return False

    def _wait_for_challenge(self, driver: webdriver.Remote) -> bool:
        """
        When a security challenge is detected, wait for the user to solve it
        via the noVNC viewer at localhost:7900.
        Returns True if the challenge was resolved.
        """
        logger.warning(
            "LinkedIn security challenge detected. "
            "User can solve it via noVNC at http://localhost:7900"
        )
        elapsed = 0
        poll_interval = 5
        while elapsed < CHALLENGE_TIMEOUT:
            time.sleep(poll_interval)
            elapsed += poll_interval
            current_url = driver.current_url
            if "checkpoint" not in current_url and "challenge" not in current_url:
                # Challenge solved — check if we're logged in
                if self._is_logged_in(driver):
                    logger.info("Security challenge solved by user via VNC")
                    return True
        logger.warning("Challenge timeout — user did not solve within %ds", CHALLENGE_TIMEOUT)
        return False

    def _login(self, driver: webdriver.Remote, username: str, password: str) -> dict[str, Any]:
        """
        Log into LinkedIn. Returns a dict with:
          - success: bool
          - challenge: bool  (True if a challenge was/is active)
          - message: str
        """
        # --- Attempt 1: try saved cookies ---
        if self._load_cookies(driver, username):
            driver.get(self.FEED_URL)
            time.sleep(3)
            if self._is_logged_in(driver):
                logger.info("LinkedIn login via saved cookies succeeded")
                return {"success": True, "challenge": False, "message": "Logged in via saved cookies"}

        # --- Attempt 2: credential login ---
        try:
            driver.get(self.LOGIN_URL)
            time.sleep(2)

            email_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            email_field.clear()
            email_field.send_keys(username)
            time.sleep(0.5)

            password_field = driver.find_element(By.ID, "password")
            password_field.clear()
            password_field.send_keys(password)
            time.sleep(0.5)

            sign_in_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            sign_in_btn.click()
            time.sleep(4)

            current_url = driver.current_url

            # Success?
            if self._is_logged_in(driver):
                self._save_cookies(driver, username)
                return {"success": True, "challenge": False, "message": "Login successful"}

            # Security challenge?
            if "checkpoint" in current_url or "challenge" in current_url:
                solved = self._wait_for_challenge(driver)
                if solved:
                    self._save_cookies(driver, username)
                    return {"success": True, "challenge": True, "message": "Challenge solved via VNC"}
                return {
                    "success": False,
                    "challenge": True,
                    "message": (
                        "LinkedIn security challenge detected. "
                        "Open http://localhost:7900 in your browser to see the Selenium "
                        "browser and solve the challenge (CAPTCHA/verification). "
                        "Then click 'Test Connection' again."
                    ),
                }

            # Bad credentials?
            try:
                error = driver.find_element(By.ID, "error-for-password")
                if error.is_displayed():
                    return {"success": False, "challenge": False, "message": "Invalid credentials"}
            except Exception:
                pass

            # Unknown state
            return {
                "success": False,
                "challenge": False,
                "message": f"Login unclear — ended at {current_url}",
            }

        except Exception as e:
            logger.error("LinkedIn login error", error=str(e))
            return {"success": False, "challenge": False, "message": f"Login error: {e}"}

    def test_connection(self, username: str, password: str) -> dict[str, Any]:
        """Test if we can log into LinkedIn with the given credentials."""
        driver = self._create_driver()
        try:
            result = self._login(driver, username, password)
            if result["success"]:
                # Get profile name from nav
                profile_name = ""
                try:
                    nav = driver.find_element(By.CSS_SELECTOR, ".global-nav__me-photo")
                    profile_name = nav.get_attribute("alt") or ""
                except Exception:
                    pass
                return {
                    "connected": True,
                    "profile_name": profile_name,
                    "message": result["message"],
                }
            else:
                return {
                    "connected": False,
                    "challenge": result.get("challenge", False),
                    "message": result["message"],
                }
        finally:
            driver.quit()

    def fetch_recent_messages(
        self, username: str, password: str, count: int = 5
    ) -> dict[str, Any]:
        """
        Fetch recent LinkedIn messaging conversations.
        Returns conversation previews, not full threads.
        """
        driver = self._create_driver()
        try:
            login_result = self._login(driver, username, password)
            if not login_result["success"]:
                return {
                    "success": False,
                    "error": login_result["message"],
                    "challenge": login_result.get("challenge", False),
                    "conversations": [],
                }

            # Navigate to messaging
            driver.get(self.MESSAGING_URL)
            time.sleep(4)

            conversations: list[dict[str, Any]] = []

            # Try to find conversation list items
            selectors = [
                "li.msg-conversation-listitem",
                ".msg-conversations-container__conversations-list li",
                ".msg-conversation-card",
                "[data-control-name='overlay.view_message']",
                ".msg-overlay-list-bubble",
            ]

            thread_items = []
            for selector in selectors:
                try:
                    WebDriverWait(driver, 8).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    thread_items = driver.find_elements(By.CSS_SELECTOR, selector)
                    if thread_items:
                        logger.info(
                            "Found conversation items",
                            selector=selector,
                            count=len(thread_items),
                        )
                        break
                except Exception:
                    continue

            if not thread_items:
                # Fallback: try to extract any conversation data from page
                logger.warning("No conversation items found with known selectors")
                # Try the messaging page body for any text
                try:
                    page_text = driver.find_element(By.TAG_NAME, "body").text
                    if "messaging" in page_text.lower():
                        return {
                            "success": True,
                            "connected": True,
                            "conversations": [],
                            "message": "Connected to LinkedIn messaging but could not parse conversations. LinkedIn may have updated their UI.",
                        }
                except Exception:
                    pass
                return {
                    "success": True,
                    "connected": True,
                    "conversations": [],
                    "message": "Connected but no conversations found.",
                }

            # Extract conversation data
            for item in thread_items[:count]:
                try:
                    convo: dict[str, Any] = {}

                    # Try to get sender name
                    name_selectors = [
                        ".msg-conversation-listitem__participant-names",
                        ".msg-conversation-card__participant-names",
                        "h3",
                        ".msg-conversation-listitem__title-row span",
                    ]
                    for ns in name_selectors:
                        try:
                            name_el = item.find_element(By.CSS_SELECTOR, ns)
                            text = name_el.text.strip()
                            if text:
                                convo["sender_name"] = text
                                break
                        except Exception:
                            continue

                    # Try to get last message preview
                    msg_selectors = [
                        ".msg-conversation-listitem__message-snippet",
                        ".msg-conversation-card__message-snippet",
                        ".msg-conversation-listitem__message-snippet-body",
                        "p",
                    ]
                    for ms in msg_selectors:
                        try:
                            msg_el = item.find_element(By.CSS_SELECTOR, ms)
                            text = msg_el.text.strip()
                            if text and text != convo.get("sender_name", ""):
                                convo["last_message"] = text
                                break
                        except Exception:
                            continue

                    # Try to get timestamp
                    time_selectors = [
                        ".msg-conversation-listitem__time-stamp",
                        ".msg-conversation-card__time-stamp",
                        "time",
                    ]
                    for ts in time_selectors:
                        try:
                            time_el = item.find_element(By.CSS_SELECTOR, ts)
                            text = time_el.text.strip()
                            if text:
                                convo["timestamp"] = text
                                break
                        except Exception:
                            continue

                    # Try to detect if unread
                    try:
                        unread = item.find_elements(
                            By.CSS_SELECTOR, ".msg-conversation-listitem__unread-dot, .notification-badge"
                        )
                        convo["unread"] = len(unread) > 0
                    except Exception:
                        convo["unread"] = False

                    if convo.get("sender_name") or convo.get("last_message"):
                        conversations.append(convo)

                except Exception as e:
                    logger.warning("Error parsing conversation item", error=str(e))
                    continue

            return {
                "success": True,
                "connected": True,
                "conversations": conversations,
                "total_found": len(thread_items),
                "message": f"Fetched {len(conversations)} conversations",
            }

        except Exception as e:
            logger.error("LinkedIn message fetch failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "conversations": [],
            }
        finally:
            driver.quit()

    # ── LinkedIn Job Search ──────────────────────────────────────

    def search_jobs(
        self,
        username: str,
        password: str,
        keywords: str,
        location: str = "",
        max_results: int = 25,
    ) -> dict[str, Any]:
        """
        Search for jobs on LinkedIn using an authenticated session.
        Returns structured job data from the LinkedIn job search page.
        """
        driver = self._create_driver()
        try:
            login_result = self._login(driver, username, password)
            if not login_result["success"]:
                return {
                    "success": False,
                    "error": login_result["message"],
                    "challenge": login_result.get("challenge", False),
                    "jobs": [],
                }

            # Build LinkedIn job search URL
            import urllib.parse

            params = urllib.parse.urlencode({
                "keywords": keywords,
                "location": location,
                "f_TPR": "r86400",  # Past 24 hours
                "sortBy": "R",  # Most relevant
            })
            search_url = f"https://www.linkedin.com/jobs/search/?{params}"
            driver.get(search_url)
            time.sleep(4)

            jobs: list[dict[str, Any]] = []

            # Try to find job cards on the authenticated LinkedIn jobs page
            card_selectors = [
                ".jobs-search-results__list-item",
                ".job-card-container",
                ".jobs-search-results-list li",
                ".scaffold-layout__list-container li",
                ".base-card",
            ]

            cards = []
            for selector in card_selectors:
                try:
                    WebDriverWait(driver, 8).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    cards = driver.find_elements(By.CSS_SELECTOR, selector)
                    if cards:
                        logger.info("Found job cards", selector=selector, count=len(cards))
                        break
                except Exception:
                    continue

            if not cards:
                logger.warning("No job cards found on LinkedIn")
                return {
                    "success": True,
                    "connected": True,
                    "jobs": [],
                    "message": "Connected but could not find job listings. LinkedIn may have updated their UI.",
                }

            # Scroll to load more results
            for _ in range(3):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(2)
                new_cards = []
                for selector in card_selectors:
                    new_cards = driver.find_elements(By.CSS_SELECTOR, selector)
                    if new_cards:
                        cards = new_cards
                        break

            for card in cards[:max_results]:
                try:
                    job: dict[str, Any] = {"source": "linkedin"}

                    # Title
                    for sel in [
                        ".job-card-list__title",
                        ".base-search-card__title",
                        "a.job-card-container__link",
                        "strong",
                        "h3",
                    ]:
                        try:
                            el = card.find_element(By.CSS_SELECTOR, sel)
                            text = el.text.strip()
                            if text:
                                job["title"] = text
                                break
                        except Exception:
                            continue

                    # Company
                    for sel in [
                        ".job-card-container__primary-description",
                        ".base-search-card__subtitle",
                        ".artdeco-entity-lockup__subtitle",
                        "h4",
                    ]:
                        try:
                            el = card.find_element(By.CSS_SELECTOR, sel)
                            text = el.text.strip()
                            if text:
                                job["company"] = text
                                break
                        except Exception:
                            continue

                    # Location
                    for sel in [
                        ".job-card-container__metadata-item",
                        ".job-search-card__location",
                        ".artdeco-entity-lockup__caption",
                    ]:
                        try:
                            el = card.find_element(By.CSS_SELECTOR, sel)
                            text = el.text.strip()
                            if text:
                                job["location"] = text
                                break
                        except Exception:
                            continue

                    # URL
                    for sel in ["a[href*='/jobs/view/']", "a.job-card-container__link", "a.base-card__full-link", "a"]:
                        try:
                            el = card.find_element(By.CSS_SELECTOR, sel)
                            href = el.get_attribute("href")
                            if href and "linkedin.com" in href:
                                job["source_url"] = href.split("?")[0]
                                source_id = href.split("/jobs/view/")[-1].split("/")[0].split("?")[0] if "/jobs/view/" in href else None
                                if source_id and source_id.isdigit():
                                    job["source_job_id"] = source_id
                                break
                        except Exception:
                            continue

                    if job.get("title") and job.get("source_url"):
                        jobs.append(job)

                except Exception as e:
                    logger.warning("Error parsing LinkedIn job card", error=str(e))
                    continue

            return {
                "success": True,
                "connected": True,
                "jobs": jobs,
                "total_found": len(cards),
                "message": f"Found {len(jobs)} jobs on LinkedIn",
            }

        except Exception as e:
            logger.error("LinkedIn job search failed", error=str(e))
            return {"success": False, "error": str(e), "jobs": []}
        finally:
            driver.quit()

    # ── LinkedIn Recruiter / People Search ───────────────────────

    def _extract_people_from_links(
        self, driver: Any, company: str,
    ) -> list[dict[str, Any]]:
        """Fallback: extract people from profile <a> links when CSS selectors fail."""
        people: list[dict[str, Any]] = []
        skip_names = {
            "home", "jobs", "messaging", "notifications", "me",
            "connect", "message", "follow", "linkedin member",
            "my network", "for business", "",
        }
        try:
            anchors = driver.find_elements(By.CSS_SELECTOR, "a[href*='/in/']")
            seen: set[str] = set()
            for anchor in anchors:
                try:
                    href = (anchor.get_attribute("href") or "").split("?")[0]
                    if "/in/" not in href or href in seen:
                        continue

                    raw = anchor.text.strip().split("\n")[0].strip()
                    # Strip connection-degree suffix: "Name · 2nd" → "Name"
                    if " ·" in raw:
                        raw = raw.split(" ·")[0].strip()
                    if raw.lower() in skip_names or len(raw) < 3:
                        continue
                    seen.add(href)

                    person: dict[str, Any] = {
                        "platform": "linkedin",
                        "name": raw,
                        "linkedin_url": href,
                        "company": company,
                    }

                    # Walk up DOM to the enclosing <li> for title / location
                    try:
                        container = anchor
                        for _ in range(8):
                            parent = container.find_element(By.XPATH, "..")
                            if parent.tag_name == "li" and len(parent.text) > len(raw) + 10:
                                container = parent
                                break
                            container = parent
                        lines = [
                            l.strip()
                            for l in container.text.split("\n")
                            if l.strip()
                        ]
                        for i, line in enumerate(lines):
                            if raw in line:
                                if (
                                    i + 1 < len(lines)
                                    and lines[i + 1].lower() not in skip_names
                                ):
                                    person["title"] = lines[i + 1]
                                if i + 2 < len(lines) and "," in lines[i + 2]:
                                    person["location"] = lines[i + 2]
                                break
                    except Exception:
                        pass

                    # Company filter — only keep people at the target company
                    title_lower = (person.get("title") or "").lower()
                    co_lower = company.lower()
                    match = co_lower in title_lower
                    first_word = co_lower.split()[0] if co_lower.strip() else ""
                    if not match and first_word and len(first_word) > 2:
                        match = first_word in title_lower
                    if match:
                        people.append(person)
                    else:
                        logger.debug(
                            "Link-fallback: skip — not at target company",
                            name=raw,
                            title=title_lower,
                            target=company,
                        )
                except Exception:
                    continue
        except Exception as e:
            logger.warning("Profile-link extraction failed", error=str(e))
        return people

    def search_people(
        self,
        username: str,
        password: str,
        company: str,
        role_keywords: str = "recruiter OR hiring manager",
        max_results: int = 10,
    ) -> dict[str, Any]:
        """
        Search for recruiters/people at a specific company on LinkedIn.
        Uses the authenticated LinkedIn People search.
        """
        driver = self._create_driver()
        try:
            login_result = self._login(driver, username, password)
            if not login_result["success"]:
                return {
                    "success": False,
                    "error": login_result["message"],
                    "challenge": login_result.get("challenge", False),
                    "people": [],
                }

            import urllib.parse

            # Search strategy: "recruiter at {company}" to find people
            # who are recruiters at the target company
            clean_keywords = role_keywords.replace(" OR ", " ").strip()
            query = f"{clean_keywords} at {company}"
            params = urllib.parse.urlencode({
                "keywords": query,
                "origin": "GLOBAL_SEARCH_HEADER",
            })
            search_url = f"https://www.linkedin.com/search/results/people/?{params}"
            logger.info("LinkedIn people search URL", url=search_url, query=query)
            driver.get(search_url)
            time.sleep(5)

            people: list[dict[str, Any]] = []

            # Find people result cards
            list_selectors = [
                ".reusable-search__result-container",
                ".search-results-container li",
                "li.reusable-search__result-container",
                ".entity-result",
            ]

            results = []
            for selector in list_selectors:
                try:
                    WebDriverWait(driver, 8).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    results = driver.find_elements(By.CSS_SELECTOR, selector)
                    if results:
                        logger.info("Found people results", selector=selector, count=len(results))
                        break
                except Exception:
                    continue

            if not results:
                # CSS selectors failed — try link-based extraction on this page
                people = self._extract_people_from_links(driver, company)
                if people:
                    logger.info(
                        "Extracted people via link fallback (keyword page)",
                        count=len(people),
                    )
                    return {
                        "success": True,
                        "connected": True,
                        "people": people,
                        "message": f"Found {len(people)} people at {company}",
                    }

                # Retry with just company name (broader search)
                # is removed — it returns random employees, not recruiters.
                # Instead, just report no results found.
                logger.warning(
                    "No people search results found",
                    query=query,
                    page_url=driver.current_url,
                )
                try:
                    body_text = driver.find_element(By.TAG_NAME, "body").text[:500]
                    logger.debug("Page body preview", text=body_text)
                except Exception:
                    pass
                return {
                    "success": True,
                    "connected": True,
                    "people": [],
                    "message": f"No recruiter results found for '{query}'",
                }

            for item in results[:max_results]:
                try:
                    person: dict[str, Any] = {"platform": "linkedin"}

                    # Name
                    for sel in [
                        ".entity-result__title-text a span[aria-hidden='true']",
                        ".entity-result__title-text a",
                        ".app-aware-link span",
                        "span.entity-result__title-text",
                    ]:
                        try:
                            el = item.find_element(By.CSS_SELECTOR, sel)
                            text = el.text.strip()
                            if text and text != "LinkedIn Member":
                                person["name"] = text
                                break
                        except Exception:
                            continue

                    # Title / Headline
                    for sel in [
                        ".entity-result__primary-subtitle",
                        ".entity-result__summary",
                        ".linked-area .entity-result__primary-subtitle",
                    ]:
                        try:
                            el = item.find_element(By.CSS_SELECTOR, sel)
                            text = el.text.strip()
                            if text:
                                person["title"] = text
                                break
                        except Exception:
                            continue

                    # LinkedIn URL
                    for sel in [
                        ".entity-result__title-text a",
                        "a.app-aware-link[href*='/in/']",
                    ]:
                        try:
                            el = item.find_element(By.CSS_SELECTOR, sel)
                            href = el.get_attribute("href")
                            if href and "/in/" in href:
                                person["linkedin_url"] = href.split("?")[0]
                                break
                        except Exception:
                            continue

                    # Location
                    for sel in [".entity-result__secondary-subtitle"]:
                        try:
                            el = item.find_element(By.CSS_SELECTOR, sel)
                            text = el.text.strip()
                            if text:
                                person["location"] = text
                                break
                        except Exception:
                            continue

                    person["company"] = company

                    if person.get("name") and person.get("linkedin_url"):
                        # Verify: check if title/headline indicates recruiter role
                        # at the target company
                        title_text = (person.get("title") or "").lower()
                        company_lower = company.lower()

                        # Check if the person's headline mentions the target company
                        company_match = company_lower in title_text
                        # Also accept if first word of company matches (e.g. "Microsoft" in "Microsoft Corporation")
                        company_first_word = company_lower.split()[0] if company_lower.strip() else ""
                        if not company_match and company_first_word and len(company_first_word) > 2:
                            company_match = company_first_word in title_text

                        # Check if title indicates a recruiting/hiring role
                        recruiter_keywords = [
                            "recruit", "hiring", "talent", "staffing",
                            "people", "hr ", "human resource",
                            "acquisition", "sourcing", "sourcer",
                        ]
                        is_recruiter = any(kw in title_text for kw in recruiter_keywords)

                        if company_match and is_recruiter:
                            people.append(person)
                            logger.debug(
                                "Recruiter verified",
                                name=person["name"],
                                title=person.get("title"),
                            )
                        elif company_match:
                            # At the company but title doesn't scream recruiter —
                            # still include but deprioritize
                            people.append(person)
                        else:
                            logger.debug(
                                "Skipping person — not at target company",
                                name=person.get("name"),
                                title=title_text,
                                target=company,
                            )

                except Exception as e:
                    logger.warning("Error parsing people result", error=str(e))
                    continue

            return {
                "success": True,
                "connected": True,
                "people": people,
                "total_found": len(results),
                "message": f"Found {len(people)} people at {company}",
            }

        except Exception as e:
            logger.error("LinkedIn people search failed", error=str(e))
            return {"success": False, "error": str(e), "people": []}
        finally:
            driver.quit()
