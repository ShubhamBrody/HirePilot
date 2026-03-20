"""
Selenium + LLM Job Application Bot

Uses Selenium for browser automation and Ollama LLM to intelligently
analyze page DOM, identify form fields, buttons, and navigate multi-step
application forms.

The LLM acts as the "eyes" — it reads the page HTML and tells Selenium
exactly what to click, fill, and where the next button is.
"""

import asyncio
import json
import random
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.llm_service import LLMService

settings = get_settings()
logger = get_logger(__name__)

# Selenium imports — use sync API since Celery tasks are sync
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


# ── LLM Prompts for DOM Analysis ──────────────────────────────────

DOM_ANALYZE_SYSTEM = (
    "You are an expert web automation assistant. "
    "You analyze HTML snippets of job application pages and return "
    "structured JSON instructions for a Selenium bot. "
    "Return ONLY valid JSON — no markdown, no commentary."
)

IDENTIFY_PAGE_TYPE_PROMPT = """Analyze this HTML from a job application page and tell me what type of page it is.

HTML (truncated):
{html}

Return JSON:
{{
  "page_type": "job_listing" | "application_form" | "login_required" | "captcha" | "success" | "error" | "unknown",
  "has_apply_button": true/false,
  "apply_button_selector": "CSS selector for the apply/submit button" or null,
  "description": "Brief description of what's on the page"
}}"""

ANALYZE_FORM_PROMPT = """Analyze this HTML from a job application form page. Identify all form fields and buttons.

HTML (truncated):
{html}

User Profile Data Available:
{user_data}

Return JSON:
{{
  "fields": [
    {{
      "selector": "CSS selector to find the field",
      "field_type": "text" | "email" | "tel" | "file" | "select" | "textarea" | "radio" | "checkbox",
      "label": "What the field is asking for",
      "value": "What value to fill from the user data, or null if unknown",
      "required": true/false
    }}
  ],
  "next_button": {{
    "selector": "CSS selector for the Next/Continue/Submit button",
    "text": "Button text",
    "is_submit": true/false
  }} or null,
  "has_file_upload": true/false,
  "file_upload_selector": "CSS selector for resume upload input" or null,
  "additional_notes": "Any warnings or observations"
}}"""


class SeleniumApplicationBot:
    """
    AI-powered job application bot using Selenium + Ollama LLM.

    Flow:
    1. Navigate to job URL
    2. LLM analyzes the page to identify the Apply button
    3. Click Apply
    4. For each form step:
       a. Get page HTML
       b. LLM identifies form fields and suggests values
       c. Selenium fills the fields
       d. LLM identifies the Next/Submit button
       e. Selenium clicks it
    5. Upload resume when file input is found
    6. Submit and confirm
    """

    def __init__(self, selenium_url: str | None = None):
        self.selenium_url = selenium_url or settings.selenium_url
        self.llm = LLMService()
        self.action_log: list[dict[str, Any]] = []
        self.daily_limit = settings.application_rate_limit_per_day

    def _get_driver(self) -> Any:
        """Create a Selenium WebDriver instance."""
        if not SELENIUM_AVAILABLE:
            raise RuntimeError("Selenium is not installed. Run: pip install selenium")

        options = ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        # Disable automation flags
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        try:
            # Try Remote WebDriver first (Docker selenium-chrome service)
            driver = webdriver.Remote(
                command_executor=self.selenium_url,
                options=options,
            )
        except Exception:
            # Fall back to local Chrome
            try:
                driver = webdriver.Chrome(options=options)
            except Exception as e:
                raise RuntimeError(
                    f"Could not connect to Selenium. "
                    f"Tried remote ({self.selenium_url}) and local Chrome. "
                    f"Error: {e}"
                )

        return driver

    def apply_to_job(
        self,
        job_url: str,
        resume_pdf_path: str,
        user_profile: dict[str, str],
        cover_letter: str | None = None,
    ) -> dict[str, Any]:
        """
        Execute the full job application flow.

        Args:
            job_url: URL of the job posting
            resume_pdf_path: Local path to the resume PDF file
            user_profile: Dict with user's info (full_name, email, phone, etc.)
            cover_letter: Optional cover letter text

        Returns:
            Dict with status, action_log, and any errors
        """
        self.action_log = []
        result: dict[str, Any] = {
            "success": False,
            "status": "unknown",
            "action_log": [],
            "error": None,
        }

        driver = None
        try:
            driver = self._get_driver()
            self._log("init", "Browser started")

            # Step 1: Navigate to job page
            self._log("navigate", f"Opening {job_url}")
            driver.get(job_url)
            self._wait(2.0, 4.0)

            # Step 2: Analyze page with LLM
            page_html = self._get_clean_html(driver)
            page_info = self._run_async(
                self._analyze_page_type(page_html)
            )
            self._log("analyze", f"Page type: {page_info.get('page_type', 'unknown')}")

            # Handle different page types
            page_type = page_info.get("page_type", "unknown")

            if page_type == "captcha":
                result["status"] = "captcha_detected"
                result["error"] = "CAPTCHA detected — manual intervention required"
                self._save_screenshot(driver, "captcha")
                return result

            if page_type == "login_required":
                result["status"] = "login_required"
                result["error"] = "Login required — please configure platform credentials"
                return result

            if page_type == "error":
                result["status"] = "page_error"
                result["error"] = "Job page returned an error"
                return result

            # Step 3: Click Apply button
            apply_selector = page_info.get("apply_button_selector")
            if apply_selector and page_info.get("has_apply_button"):
                self._log("click_apply", f"Clicking apply: {apply_selector}")
                try:
                    apply_btn = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, apply_selector))
                    )
                    apply_btn.click()
                    self._wait(2.0, 3.0)
                except Exception as e:
                    # Try common fallback selectors
                    clicked = self._try_common_apply_buttons(driver)
                    if not clicked:
                        result["status"] = "error"
                        result["error"] = f"Could not click Apply button: {e}"
                        return result

            # Step 4: Handle multi-step application form
            max_steps = 12
            for step in range(max_steps):
                self._log("form_step", f"Processing form step {step + 1}")
                self._wait(1.5, 2.5)

                # Get current page HTML
                form_html = self._get_clean_html(driver)

                # Check if we've reached a success page
                success_check = self._run_async(self._analyze_page_type(form_html))
                if success_check.get("page_type") == "success":
                    result["success"] = True
                    result["status"] = "submitted"
                    self._log("success", "Application submitted successfully!")
                    break

                if success_check.get("page_type") == "captcha":
                    result["status"] = "captcha_detected"
                    result["error"] = "CAPTCHA detected during form fill"
                    self._save_screenshot(driver, f"captcha_step_{step}")
                    break

                # Analyze form fields with LLM
                form_instructions = self._run_async(
                    self._analyze_form(form_html, user_profile)
                )

                # Fill fields
                fields_filled = 0
                for field in form_instructions.get("fields", []):
                    value = field.get("value")
                    if not value:
                        continue
                    try:
                        self._fill_field(driver, field)
                        fields_filled += 1
                        self._wait(0.3, 0.8)
                    except Exception as e:
                        self._log("field_error", f"Could not fill {field.get('label')}: {e}")

                self._log("fields_filled", f"Filled {fields_filled} fields in step {step + 1}")

                # Upload resume if file input found
                if form_instructions.get("has_file_upload") and resume_pdf_path:
                    file_selector = form_instructions.get("file_upload_selector", "input[type='file']")
                    try:
                        file_input = driver.find_element(By.CSS_SELECTOR, file_selector)
                        file_input.send_keys(resume_pdf_path)
                        self._log("upload", "Resume uploaded")
                        self._wait(1.0, 2.0)
                    except Exception as e:
                        self._log("upload_error", f"Resume upload failed: {e}")

                # Fill cover letter if applicable
                if cover_letter:
                    self._try_fill_cover_letter(driver, cover_letter)

                # Click Next/Submit button
                next_btn = form_instructions.get("next_button")
                if next_btn and next_btn.get("selector"):
                    is_submit = next_btn.get("is_submit", False)
                    try:
                        btn = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable(
                                (By.CSS_SELECTOR, next_btn["selector"])
                            )
                        )
                        self._wait(0.5, 1.5)
                        btn.click()
                        self._log(
                            "submit" if is_submit else "next",
                            f"Clicked {'Submit' if is_submit else 'Next'}: {next_btn.get('text', '')}"
                        )
                        self._wait(2.0, 4.0)

                        if is_submit:
                            # Check for success after submission
                            self._wait(2.0, 3.0)
                            final_html = self._get_clean_html(driver)
                            final_check = self._run_async(self._analyze_page_type(final_html))
                            if final_check.get("page_type") == "success":
                                result["success"] = True
                                result["status"] = "submitted"
                                self._log("success", "Application submitted!")
                            else:
                                result["success"] = True
                                result["status"] = "likely_submitted"
                                self._log("likely_success", "Submit clicked — likely submitted")
                            break
                    except Exception as e:
                        self._log("button_error", f"Could not click button: {e}")
                        # Try common next/submit buttons
                        if not self._try_common_next_buttons(driver):
                            result["status"] = "stuck"
                            result["error"] = f"Could not advance form at step {step + 1}"
                            self._save_screenshot(driver, f"stuck_step_{step}")
                            break
                else:
                    # No next button found — might be done or stuck
                    if not self._try_common_next_buttons(driver):
                        self._log("no_button", "No next/submit button found")
                        break

            if result["status"] == "unknown":
                result["status"] = "completed_unknown"
                result["error"] = "Completed all steps but couldn't confirm submission"

        except Exception as e:
            logger.error("Selenium bot failed", url=job_url, error=str(e))
            result["status"] = "error"
            result["error"] = str(e)

        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass
            result["action_log"] = self.action_log

        return result

    # ── LLM Integration ──────────────────────────────────────────

    async def _analyze_page_type(self, html: str) -> dict[str, Any]:
        """Ask LLM to identify the page type and find Apply button."""
        try:
            prompt = IDENTIFY_PAGE_TYPE_PROMPT.format(html=html[:12000])
            return await self.llm.generate_json(prompt, system=DOM_ANALYZE_SYSTEM)
        except Exception as e:
            logger.error("LLM page analysis failed", error=str(e))
            return {"page_type": "unknown", "has_apply_button": False}

    async def _analyze_form(
        self, html: str, user_profile: dict[str, str]
    ) -> dict[str, Any]:
        """Ask LLM to identify form fields and map user data to them."""
        try:
            user_data = json.dumps(
                {k: v for k, v in user_profile.items() if v},
                indent=2,
            )
            prompt = ANALYZE_FORM_PROMPT.format(
                html=html[:12000],
                user_data=user_data,
            )
            return await self.llm.generate_json(prompt, system=DOM_ANALYZE_SYSTEM)
        except Exception as e:
            logger.error("LLM form analysis failed", error=str(e))
            return {"fields": [], "next_button": None}

    # ── Selenium Helpers ─────────────────────────────────────────

    def _fill_field(self, driver: Any, field: dict[str, Any]) -> None:
        """Fill a single form field based on LLM instructions."""
        selector = field["selector"]
        value = field["value"]
        field_type = field.get("field_type", "text")

        el = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )

        if field_type == "select":
            from selenium.webdriver.support.ui import Select
            select = Select(el)
            try:
                select.select_by_visible_text(value)
            except Exception:
                try:
                    select.select_by_value(value)
                except Exception:
                    # Try partial match
                    for option in select.options:
                        if value.lower() in option.text.lower():
                            select.select_by_visible_text(option.text)
                            break

        elif field_type == "file":
            el.send_keys(value)

        elif field_type in ("radio", "checkbox"):
            if not el.is_selected():
                el.click()

        elif field_type == "textarea":
            el.clear()
            # Type with human-like speed
            for char in value:
                el.send_keys(char)
                self._wait(0.02, 0.06)

        else:
            el.clear()
            for char in value:
                el.send_keys(char)
                self._wait(0.02, 0.06)

    def _try_common_apply_buttons(self, driver: Any) -> bool:
        """Try clicking common Apply button selectors."""
        selectors = [
            "button[data-control-name*='apply']",
            "button.jobs-apply-button",
            "a[data-tracking-control-name*='apply']",
            "button:has-text('Apply')",
            "a:has-text('Apply Now')",
            "button:has-text('Easy Apply')",
            "[class*='apply-button']",
            "[class*='applyButton']",
        ]
        for sel in selectors:
            try:
                btn = driver.find_element(By.CSS_SELECTOR, sel)
                if btn.is_displayed():
                    btn.click()
                    self._log("fallback_apply", f"Clicked apply via: {sel}")
                    return True
            except Exception:
                continue
        return False

    def _try_common_next_buttons(self, driver: Any) -> bool:
        """Try clicking common Next/Submit buttons."""
        selectors = [
            "button[type='submit']",
            "button[aria-label*='Submit']",
            "button[aria-label*='Next']",
            "button[aria-label*='Continue']",
            "button:has-text('Submit')",
            "button:has-text('Next')",
            "button:has-text('Continue')",
            "[class*='submit']",
        ]
        for sel in selectors:
            try:
                btn = driver.find_element(By.CSS_SELECTOR, sel)
                if btn.is_displayed():
                    btn.click()
                    self._log("fallback_next", f"Clicked next via: {sel}")
                    return True
            except Exception:
                continue
        return False

    def _try_fill_cover_letter(self, driver: Any, cover_letter: str) -> None:
        """Try to find and fill a cover letter field."""
        selectors = [
            "textarea[name*='cover']",
            "textarea[aria-label*='cover letter']",
            "textarea[placeholder*='cover letter']",
            "#cover-letter",
            "textarea[name*='letter']",
        ]
        for sel in selectors:
            try:
                el = driver.find_element(By.CSS_SELECTOR, sel)
                if el.is_displayed():
                    el.clear()
                    el.send_keys(cover_letter)
                    self._log("cover_letter", "Cover letter filled")
                    return
            except Exception:
                continue

    def _get_clean_html(self, driver: Any) -> str:
        """Get a cleaned version of the page HTML for LLM analysis."""
        try:
            # Get the body HTML (skip head/scripts for token efficiency)
            body = driver.find_element(By.TAG_NAME, "body")
            html = body.get_attribute("innerHTML")

            # Remove script and style tags to reduce noise
            import re
            html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
            html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL)
            html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)
            # Remove excessive whitespace
            html = re.sub(r"\s+", " ", html)

            return html[:15000]  # Truncate for LLM context
        except Exception:
            return driver.page_source[:15000]

    def _save_screenshot(self, driver: Any, name: str) -> str | None:
        """Save a screenshot for debugging."""
        try:
            path = f"/tmp/hirepilot_screenshot_{name}_{int(datetime.now(UTC).timestamp())}.png"
            driver.save_screenshot(path)
            self._log("screenshot", f"Saved: {path}")
            return path
        except Exception:
            return None

    # ── Utility ──────────────────────────────────────────────────

    def _wait(self, min_sec: float, max_sec: float) -> None:
        """Human-like random delay."""
        import time
        time.sleep(random.uniform(min_sec, max_sec))

    def _log(self, action: str, detail: str) -> None:
        """Log an automation action."""
        entry = {
            "action": action,
            "detail": detail,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        self.action_log.append(entry)
        logger.info("SeleniumBot", **entry)

    @staticmethod
    def _run_async(coro: Any) -> Any:
        """Run an async coroutine from sync context."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, coro)
                    return future.result()
            return loop.run_until_complete(coro)
        except RuntimeError:
            return asyncio.run(coro)
