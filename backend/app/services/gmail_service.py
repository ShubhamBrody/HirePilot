"""
Gmail Service

Connects to Gmail via Google API OAuth2, searches for job-related emails,
and returns structured email data for the Email Checker Agent.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


class GmailService:
    """
    Reads emails from Gmail using Google API.
    Requires a user's refresh token obtained via OAuth2 consent.
    """

    def __init__(self) -> None:
        self.client_id = settings.gmail_client_id
        self.client_secret = settings.gmail_client_secret.get_secret_value()
        self.scopes = settings.gmail_scopes.split(",")

    async def search_job_emails(
        self,
        refresh_token: str,
        max_results: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Search Gmail for job-related emails from the last 7 days.
        Returns list of {subject, from, snippet, date, message_id}.
        """
        import httpx

        # Exchange refresh token for access token
        access_token = await self._get_access_token(refresh_token)
        if not access_token:
            raise ValueError("Failed to get Gmail access token")

        # Search for job-related emails
        query = (
            "newer_than:7d ("
            "subject:(interview OR offer OR rejection OR application OR "
            "\"next steps\" OR \"coding challenge\" OR assessment OR "
            "\"we regret\" OR congratulations OR shortlisted) "
            "OR from:(recruiting OR talent OR careers OR hr OR hiring))"
        )

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"q": query, "maxResults": max_results},
            )
            resp.raise_for_status()
            messages = resp.json().get("messages", [])

            emails: list[dict[str, Any]] = []
            for msg in messages:
                detail = await self._get_message(client, access_token, msg["id"])
                if detail:
                    emails.append(detail)

        return emails

    async def _get_access_token(self, refresh_token: str) -> str | None:
        """Exchange refresh token for a short-lived access token."""
        import httpx

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            if resp.status_code == 200:
                return resp.json().get("access_token")
            logger.error("Gmail token refresh failed", status=resp.status_code)
            return None

    @staticmethod
    async def _get_message(
        client: Any,
        access_token: str,
        message_id: str,
    ) -> dict[str, Any] | None:
        """Fetch a single message's metadata and snippet."""
        resp = await client.get(
            f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"format": "metadata", "metadataHeaders": ["Subject", "From", "Date"]},
        )
        if resp.status_code != 200:
            return None

        data = resp.json()
        headers = {h["name"]: h["value"] for h in data.get("payload", {}).get("headers", [])}

        date_str = headers.get("Date", "")
        try:
            # Parse various date formats
            email_date = datetime.now(UTC)
        except Exception:
            email_date = datetime.now(UTC)

        return {
            "message_id": message_id,
            "subject": headers.get("Subject", "(no subject)"),
            "from": headers.get("From", ""),
            "date": email_date,
            "snippet": data.get("snippet", ""),
        }
