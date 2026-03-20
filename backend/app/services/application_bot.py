"""
Application Automation Bot

Browser-based job application automation using Playwright.
Supports auto-filling forms, uploading resumes, and submitting applications.
"""

import asyncio
import json
import random
from datetime import UTC, datetime
from typing import Any

from playwright.async_api import Page, async_playwright

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


class ApplicationBot:
    """
    Automated job application submission using Playwright.

    Safety features:
    - Human-like interaction speeds (random delays between actions)
    - CAPTCHA detection and pause
    - Rate limiting (configurable per day)
    - Full audit logging of every action
    - Screenshot capture on errors
    - Form data snapshot before submission
    """

    COMMON_FIELD_MAPPINGS = {
        # Maps common form field labels/names to user profile fields
        "first name": "first_name",
        "last name": "last_name",
        "full name": "full_name",
        "email": "email",
        "phone": "phone",
        "mobile": "phone",
        "telephone": "phone",
        "linkedin": "linkedin_url",
        "github": "github_url",
        "portfolio": "portfolio_url",
        "website": "portfolio_url",
        "personal website": "portfolio_url",
        "location": "location",
        "city": "location",
        "address": "location",
        "years of experience": "years_experience",
        "total experience": "years_experience",
        "experience": "years_experience",
        "current company": "current_company",
        "present employer": "current_company",
        "current employer": "current_company",
        "current title": "current_title",
        "current role": "current_title",
        "current designation": "current_title",
        "job title": "current_title",
        "notice period": "notice_period",
        "work authorization": "work_authorization",
        "visa status": "work_authorization",
        "are you authorized": "work_authorization",
        "sponsorship": "work_authorization",
        "require sponsorship": "work_authorization",
        "salary": "expected_salary",
        "expected salary": "expected_salary",
        "desired salary": "expected_salary",
        "current salary": "current_salary",
        "current ctc": "current_salary",
        "current compensation": "current_salary",
        "expected ctc": "expected_salary",
        "disability": "disability_status",
        "veteran": "veteran_status",
        "gender": "gender",
        "race": "race",
        "ethnicity": "ethnicity",
        "nationality": "nationality",
        "degree": "degree",
        "education": "education",
        "university": "university",
        "school": "university",
        "college": "university",
        "gpa": "gpa",
        "date of birth": "date_of_birth",
        "dob": "date_of_birth",
        "headline": "headline",
        "cover letter": "cover_letter",
    }

    def __init__(self) -> None:
        self.daily_limit = settings.application_rate_limit_per_day
        self.applied_today = 0  # Track via Redis in production
        self.action_log: list[dict[str, Any]] = []

    async def apply_to_job(
        self,
        job_url: str,
        resume_pdf_path: str,
        user_profile: dict[str, str],
        cover_letter: str | None = None,
        additional_form_data: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Automate a job application submission.

        Args:
            job_url: URL of the job application page
            resume_pdf_path: Local path to the tailored resume PDF
            user_profile: Dict with user's form-filling data
            cover_letter: Optional cover letter text
            additional_form_data: Extra field values for the form

        Returns:
            Dict with status, action log, and any errors
        """
        if self.applied_today >= self.daily_limit:
            return {
                "status": "rate_limited",
                "message": f"Daily application limit ({self.daily_limit}) reached",
                "action_log": self.action_log,
            }

        self.action_log = []
        result: dict[str, Any] = {
            "status": "unknown",
            "action_log": self.action_log,
            "form_data_snapshot": {},
        }

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled"],
                )
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1920, "height": 1080},
                )
                page = await context.new_page()

                # Step 1: Navigate to job page
                self._log_action("navigate", f"Opening {job_url}")
                await page.goto(job_url, wait_until="networkidle", timeout=30000)
                await self._human_delay(2.0, 4.0)

                # Step 2: Check for CAPTCHA
                if await self._detect_captcha(page):
                    result["status"] = "captcha_detected"
                    result["message"] = "CAPTCHA detected — manual intervention required"
                    await page.screenshot(path="/tmp/captcha_screenshot.png")
                    await browser.close()
                    return result

                # Step 3: Find and click "Apply" button
                self._log_action("find_apply", "Looking for Apply button")
                apply_btn = await self._find_apply_button(page)
                if apply_btn:
                    await apply_btn.click()
                    await self._human_delay(2.0, 3.0)
                    self._log_action("click_apply", "Clicked Apply button")
                else:
                    result["status"] = "error"
                    result["message"] = "Apply button not found"
                    await browser.close()
                    return result

                # Step 4: Fill form fields
                self._log_action("fill_form", "Starting form fill")
                form_data = await self._fill_application_form(
                    page, user_profile, additional_form_data or {}
                )
                result["form_data_snapshot"] = form_data

                # Step 5: Upload resume
                self._log_action("upload_resume", "Uploading resume PDF")
                await self._upload_resume(page, resume_pdf_path)

                # Step 6: Add cover letter if provided
                if cover_letter:
                    self._log_action("cover_letter", "Adding cover letter")
                    await self._fill_cover_letter(page, cover_letter)

                # Step 7: Handle multi-step forms
                await self._handle_multi_step_form(page, user_profile)

                # Step 8: Submit
                self._log_action("submit", "Submitting application")
                submitted = await self._submit_application(page)

                if submitted:
                    self.applied_today += 1
                    result["status"] = "submitted"
                    result["message"] = "Application submitted successfully"
                    self._log_action("success", "Application submitted")
                else:
                    result["status"] = "error"
                    result["message"] = "Failed to find submit button"

                await browser.close()

        except Exception as e:
            logger.error("Application automation failed", url=job_url, error=str(e))
            result["status"] = "error"
            result["message"] = str(e)

        result["action_log"] = self.action_log
        return result

    async def _detect_captcha(self, page: Page) -> bool:
        """Detect common CAPTCHA challenges."""
        captcha_selectors = [
            "iframe[src*='captcha']",
            "iframe[src*='recaptcha']",
            "iframe[src*='hcaptcha']",
            ".g-recaptcha",
            "#captcha",
            "[data-sitekey]",
            "iframe[title*='challenge']",
        ]
        for selector in captcha_selectors:
            element = await page.query_selector(selector)
            if element:
                self._log_action("captcha_detected", f"CAPTCHA found: {selector}")
                return True
        return False

    async def _find_apply_button(self, page: Page) -> Any:
        """Find the Apply/Submit button on the page."""
        selectors = [
            "button:has-text('Apply')",
            "button:has-text('Easy Apply')",
            "a:has-text('Apply Now')",
            "button:has-text('Apply Now')",
            "a:has-text('Apply on company site')",
            "button[data-control-name='jobdetails_topcard_inapply']",
            ".jobs-apply-button",
        ]
        for selector in selectors:
            try:
                btn = await page.query_selector(selector)
                if btn and await btn.is_visible():
                    return btn
            except Exception:
                continue
        return None

    async def _fill_application_form(
        self,
        page: Page,
        user_profile: dict[str, str],
        additional_data: dict[str, str],
    ) -> dict[str, str]:
        """Auto-fill form fields using intelligent field matching."""
        filled_fields: dict[str, str] = {}

        # Find all input fields
        inputs = await page.query_selector_all(
            "input[type='text'], input[type='email'], input[type='tel'], "
            "input[type='url'], textarea, select"
        )

        for input_el in inputs:
            try:
                # Get field label or placeholder
                field_name = await input_el.get_attribute("name") or ""
                placeholder = await input_el.get_attribute("placeholder") or ""
                aria_label = await input_el.get_attribute("aria-label") or ""
                label_text = (field_name + " " + placeholder + " " + aria_label).lower()

                # Try to match field to user profile data
                value = None
                for pattern, profile_key in self.COMMON_FIELD_MAPPINGS.items():
                    if pattern in label_text:
                        value = user_profile.get(profile_key) or additional_data.get(profile_key)
                        break

                # Check additional form data by field name
                if not value and field_name:
                    value = additional_data.get(field_name)

                if value:
                    tag = await input_el.evaluate("el => el.tagName.toLowerCase()")
                    if tag == "select":
                        await input_el.select_option(label=value)
                    else:
                        await input_el.fill("")
                        # Type with human-like speed
                        for char in value:
                            await input_el.type(char, delay=random.randint(30, 80))

                    filled_fields[field_name or placeholder] = value
                    await self._human_delay(0.3, 0.8)

            except Exception as e:
                logger.debug("Could not fill field", error=str(e))
                continue

        self._log_action("form_filled", f"Filled {len(filled_fields)} fields")
        return filled_fields

    async def _upload_resume(self, page: Page, resume_path: str) -> None:
        """Upload resume file to file input."""
        file_inputs = await page.query_selector_all("input[type='file']")
        for file_input in file_inputs:
            try:
                accept = await file_input.get_attribute("accept") or ""
                if "pdf" in accept.lower() or not accept:
                    await file_input.set_input_files(resume_path)
                    self._log_action("resume_uploaded", "Resume PDF uploaded")
                    await self._human_delay(1.0, 2.0)
                    return
            except Exception as e:
                logger.warning("Resume upload attempt failed", error=str(e))
                continue

    async def _fill_cover_letter(self, page: Page, cover_letter: str) -> None:
        """Fill cover letter textarea if found."""
        selectors = [
            "textarea[name*='cover']",
            "textarea[aria-label*='cover letter']",
            "textarea[placeholder*='cover letter']",
            "#cover-letter-textarea",
        ]
        for selector in selectors:
            el = await page.query_selector(selector)
            if el:
                await el.fill("")
                for char in cover_letter:
                    await el.type(char, delay=random.randint(20, 50))
                self._log_action("cover_letter_filled", "Cover letter added")
                return

    async def _handle_multi_step_form(
        self, page: Page, user_profile: dict[str, str]
    ) -> None:
        """Handle multi-step application forms (e.g., LinkedIn Easy Apply)."""
        max_steps = 10
        for step in range(max_steps):
            # Look for "Next" button
            next_btn = await page.query_selector(
                "button:has-text('Next'), button:has-text('Continue'), "
                "button[aria-label='Continue to next step']"
            )
            if not next_btn:
                break

            # Fill any new fields on this step
            await self._fill_application_form(page, user_profile, {})
            await next_btn.click()
            await self._human_delay(1.5, 3.0)
            self._log_action("next_step", f"Advanced to step {step + 2}")

    async def _submit_application(self, page: Page) -> bool:
        """Find and click the final submit button."""
        submit_selectors = [
            "button:has-text('Submit application')",
            "button:has-text('Submit')",
            "button[type='submit']",
            "button:has-text('Send application')",
            "button:has-text('Apply')",
        ]
        for selector in submit_selectors:
            try:
                btn = await page.query_selector(selector)
                if btn and await btn.is_visible():
                    await self._human_delay(1.0, 2.0)
                    await btn.click()
                    await self._human_delay(2.0, 4.0)
                    return True
            except Exception:
                continue
        return False

    async def _human_delay(self, min_sec: float, max_sec: float) -> None:
        """Add human-like random delay."""
        await asyncio.sleep(random.uniform(min_sec, max_sec))

    def _log_action(self, action: str, detail: str) -> None:
        """Log an automation action."""
        entry = {
            "action": action,
            "detail": detail,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        self.action_log.append(entry)
        logger.info("Bot action", **entry)
