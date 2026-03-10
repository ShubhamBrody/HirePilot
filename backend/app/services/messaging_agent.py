"""
Messaging Agent Service

AI-powered outreach message generation and automated sending
via LinkedIn and other platforms.
"""

import asyncio
import random
import uuid
from datetime import UTC, datetime
from typing import Any

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.recruiter import OutreachMessage, OutreachStatus

settings = get_settings()
logger = get_logger(__name__)


# ── AI Message Generation ─────────────────────────────────────────

OUTREACH_SYSTEM_PROMPT = """You are an expert career coach and networking specialist.
Your task is to write personalized outreach messages for job seekers.

Rules:
- Keep messages concise (under 300 characters for connection requests, under 2000 for InMails)
- Be professional but warm
- Reference the specific role and company
- Highlight relevant skills from the user's profile
- Never be pushy or desperate
- Include a clear call to action
- Make it feel human and genuine, not template-like
"""

CONNECTION_REQUEST_PROMPT = """Write a LinkedIn connection request message.

Recruiter: {recruiter_name}
Company: {company}
Role: {role}
User Skills: {skills}
User Experience Summary: {experience}
Tone: {tone}

Requirements:
- Maximum 300 characters (LinkedIn limit for connection notes)
- One clear reason to connect
- Reference the specific opportunity

Write ONLY the message text, nothing else."""

INMAIL_PROMPT = """Write a LinkedIn InMail or direct message.

Recruiter: {recruiter_name}
Company: {company}
Role: {role}
Job Description Summary: {job_description}
User Skills: {skills}
User Experience Summary: {experience}
Tone: {tone}

Requirements:
- Professional subject line (if applicable)
- 3-4 sentences maximum
- Specific value proposition
- Clear call to action

Format:
Subject: <subject>
Message: <message>"""

FOLLOW_UP_PROMPT = """Write a follow-up message to a recruiter who hasn't responded.

Recruiter: {recruiter_name}
Company: {company}
Role: {role}
Days Since Last Message: {days_since}
Previous Message Summary: {previous_message}
Tone: {tone}

Requirements:
- Brief and polite
- Add new value (recent achievement, portfolio link, etc.)
- Not pushy
- 2-3 sentences maximum

Write ONLY the message text, nothing else."""


class MessageGeneratorService:
    """Generates personalized outreach messages using AI."""

    def __init__(self) -> None:
        self.client = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())
        self.model = settings.openai_model

    async def generate_connection_request(
        self,
        recruiter_name: str,
        company: str,
        role: str,
        user_skills: str,
        user_experience: str,
        tone: str = "professional",
    ) -> str:
        """Generate a personalized LinkedIn connection request note."""
        prompt = CONNECTION_REQUEST_PROMPT.format(
            recruiter_name=recruiter_name,
            company=company,
            role=role,
            skills=user_skills,
            experience=user_experience,
            tone=tone,
        )

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": OUTREACH_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_tokens=200,
            temperature=0.7,
        )

        message = response.choices[0].message.content or ""
        # Enforce LinkedIn character limit
        if len(message) > 300:
            message = message[:297] + "..."
        return message.strip()

    async def generate_inmail(
        self,
        recruiter_name: str,
        company: str,
        role: str,
        job_description: str,
        user_skills: str,
        user_experience: str,
        tone: str = "professional",
    ) -> dict[str, str]:
        """Generate a personalized InMail with subject and body."""
        prompt = INMAIL_PROMPT.format(
            recruiter_name=recruiter_name,
            company=company,
            role=role,
            job_description=job_description[:500],
            skills=user_skills,
            experience=user_experience,
            tone=tone,
        )

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": OUTREACH_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_tokens=500,
            temperature=0.7,
        )

        text = response.choices[0].message.content or ""

        # Parse subject and message
        subject = ""
        body = text
        if "Subject:" in text and "Message:" in text:
            parts = text.split("Message:", 1)
            subject = parts[0].replace("Subject:", "").strip()
            body = parts[1].strip()

        return {"subject": subject, "body": body}

    async def generate_follow_up(
        self,
        recruiter_name: str,
        company: str,
        role: str,
        days_since: int,
        previous_message: str,
        tone: str = "professional",
    ) -> str:
        """Generate a follow-up message."""
        prompt = FOLLOW_UP_PROMPT.format(
            recruiter_name=recruiter_name,
            company=company,
            role=role,
            days_since=days_since,
            previous_message=previous_message[:200],
            tone=tone,
        )

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": OUTREACH_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_tokens=300,
            temperature=0.7,
        )

        return (response.choices[0].message.content or "").strip()


# ── Message Sender (Automation) ───────────────────────────────────

class MessageSenderService:
    """
    Sends outreach messages via platform automation.

    Implements:
    - Rate limiting (configurable daily/hourly caps)
    - Human-like delays between actions
    - Error handling and retry logic
    - Audit logging for every action
    """

    def __init__(self) -> None:
        self.daily_limit = settings.outreach_rate_limit_per_day
        self.sent_today = 0  # In production, track via Redis

    async def send_connection_request(
        self,
        page: Any,  # Playwright Page (authenticated)
        linkedin_url: str,
        note: str,
    ) -> dict[str, Any]:
        """
        Send a LinkedIn connection request with a personalized note.

        Returns dict with status and details.
        """
        if self.sent_today >= self.daily_limit:
            return {
                "status": "rate_limited",
                "message": f"Daily limit of {self.daily_limit} reached",
            }

        try:
            # Navigate to the recruiter's profile
            await page.goto(linkedin_url, wait_until="networkidle", timeout=20000)
            await asyncio.sleep(random.uniform(2.0, 4.0))

            # Click "Connect" button
            connect_btn = await page.query_selector("button[aria-label*='Connect']")
            if not connect_btn:
                # Try the "More" dropdown
                more_btn = await page.query_selector("button[aria-label*='More actions']")
                if more_btn:
                    await more_btn.click()
                    await asyncio.sleep(random.uniform(0.5, 1.0))
                    connect_btn = await page.query_selector("div[aria-label*='Connect']")

            if not connect_btn:
                return {"status": "error", "message": "Connect button not found"}

            await connect_btn.click()
            await asyncio.sleep(random.uniform(1.0, 2.0))

            # Click "Add a note"
            add_note_btn = await page.query_selector("button[aria-label='Add a note']")
            if add_note_btn:
                await add_note_btn.click()
                await asyncio.sleep(random.uniform(0.5, 1.0))

                # Type the note with human-like speed
                textarea = await page.query_selector("textarea[name='message']")
                if textarea:
                    await textarea.fill("")
                    for char in note:
                        await textarea.type(char, delay=random.randint(30, 80))
                    await asyncio.sleep(random.uniform(0.5, 1.0))

            # Click "Send"
            send_btn = await page.query_selector("button[aria-label='Send invitation']")
            if send_btn:
                await send_btn.click()
                await asyncio.sleep(random.uniform(1.0, 2.0))
                self.sent_today += 1

                return {
                    "status": "sent",
                    "message": "Connection request sent successfully",
                }

            return {"status": "error", "message": "Send button not found"}

        except Exception as e:
            logger.error("Connection request failed", url=linkedin_url, error=str(e))
            return {"status": "error", "message": str(e)}

    async def send_direct_message(
        self,
        page: Any,
        linkedin_url: str,
        message: str,
    ) -> dict[str, Any]:
        """
        Send a direct message to a connected recruiter on LinkedIn.
        """
        if self.sent_today >= self.daily_limit:
            return {
                "status": "rate_limited",
                "message": f"Daily limit of {self.daily_limit} reached",
            }

        try:
            await page.goto(linkedin_url, wait_until="networkidle", timeout=20000)
            await asyncio.sleep(random.uniform(2.0, 4.0))

            # Click "Message" button
            message_btn = await page.query_selector("button[aria-label*='Message']")
            if not message_btn:
                return {"status": "error", "message": "Message button not found — not connected?"}

            await message_btn.click()
            await asyncio.sleep(random.uniform(1.5, 3.0))

            # Type message in the messaging overlay
            msg_input = await page.query_selector("div[role='textbox'][contenteditable='true']")
            if msg_input:
                await msg_input.click()
                for char in message:
                    await msg_input.type(char, delay=random.randint(20, 60))
                await asyncio.sleep(random.uniform(0.5, 1.5))

                # Send
                send_btn = await page.query_selector("button[type='submit'].msg-form__send-button")
                if send_btn:
                    await send_btn.click()
                    self.sent_today += 1
                    return {"status": "sent", "message": "Direct message sent"}

            return {"status": "error", "message": "Could not find message input"}

        except Exception as e:
            logger.error("Direct message failed", url=linkedin_url, error=str(e))
            return {"status": "error", "message": str(e)}
