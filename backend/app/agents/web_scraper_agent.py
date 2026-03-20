"""
Web Scraper Agent

Intelligent page analyzer: given a URL, loads it with Selenium,
extracts clean HTML, and uses LLM to identify form fields,
buttons, navigation, and required details.
"""

from __future__ import annotations

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.core.logging import get_logger

logger = get_logger(__name__)

PAGE_ANALYSIS_SYSTEM = (
    "You are a web page analyst. Given HTML, identify: "
    "1. page_type: job_listing | application_form | login_required | captcha | other "
    "2. form_fields: [{name, type, label, required, selector}] "
    "3. buttons: [{text, purpose, selector}] "
    "4. navigation: next steps to reach the application form "
    "5. required_info: what details the user needs to provide "
    "Return JSON with these keys."
)


class WebScraperAgent(BaseAgent):
    name = "web_scraper"
    description = "Analyze any web page to identify forms, fields, buttons for automation"
    max_runs_per_hour = 20
    max_runs_per_day = 100

    async def execute(self, context: AgentContext) -> AgentResult:
        from app.services.llm_service import LLMService
        from app.services.selenium_bot import SeleniumApplicationBot

        url = context.params.get("url")
        if not url:
            return AgentResult(success=False, errors=["url is required"])

        llm = context.llm_service or LLMService()
        bot = SeleniumApplicationBot()

        try:
            driver = bot._get_driver()
            driver.get(url)
            driver.implicitly_wait(5)
            clean_html = bot._get_clean_html(driver)
            driver.quit()
        except Exception as e:
            return AgentResult(success=False, errors=[f"Failed to load page: {e}"])

        try:
            prompt = f"Analyze this web page HTML:\n\n{clean_html[:8000]}"
            analysis = await llm.generate_json(prompt, system=PAGE_ANALYSIS_SYSTEM)
            if not isinstance(analysis, dict):
                analysis = {"raw": str(analysis)}
        except Exception as e:
            return AgentResult(success=False, errors=[f"LLM analysis failed: {e}"])

        return AgentResult(
            success=True,
            data={"url": url, "analysis": analysis},
            items_processed=1,
        )
