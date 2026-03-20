"""
Tests — Recruiter Verification & No-Fake Fallback

Tests:
1. verify_recruiter_profiles filters out non-recruiters (mocked LLM)
2. RecruiterFinderService.find_recruiters returns empty (no fakes)
3. Recruiter list with company filter
"""

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.llm_service import LLMService
from app.services.recruiter_finder import RecruiterFinderService

pytestmark = pytest.mark.asyncio


SAMPLE_PROFILES = [
    {"name": "Alice Smith", "title": "Senior Technical Recruiter at Google", "company": "Google"},
    {"name": "Bob Jones", "title": "Software Engineer at Google", "company": "Google"},
    {"name": "Carol Davis", "title": "Talent Acquisition Partner at Google", "company": "Google"},
    {"name": "Dan Brown", "title": "Product Manager at Google", "company": "Google"},
    {"name": "Eve White", "title": "Consultant", "company": "Freelance"},
]


class TestVerifyRecruiterProfiles:
    """Unit tests for LLM-based recruiter verification."""

    async def test_filters_non_recruiters(self):
        """LLM identifies only actual recruiters from profile list."""
        llm = LLMService()

        # LLM returns indices 1 and 3 (Alice=recruiter, Carol=TA)
        mock_response = json.dumps([1, 3])
        with patch.object(llm, "generate", new_callable=AsyncMock, return_value=mock_response):
            result = await llm.verify_recruiter_profiles(
                SAMPLE_PROFILES, "Google", "recruiter"
            )

        names = [r["name"] for r in result]
        assert "Alice Smith" in names
        assert "Carol Davis" in names
        assert "Bob Jones" not in names
        assert "Dan Brown" not in names
        assert "Eve White" not in names

    async def test_returns_empty_when_none_qualify(self):
        """LLM returns empty array → no recruiters pass."""
        llm = LLMService()

        mock_response = json.dumps([])
        with patch.object(llm, "generate", new_callable=AsyncMock, return_value=mock_response):
            result = await llm.verify_recruiter_profiles(
                SAMPLE_PROFILES, "Google", "recruiter"
            )

        assert result == []

    async def test_returns_all_on_llm_failure(self):
        """If LLM fails, fall back to returning all (fail-open)."""
        llm = LLMService()

        with patch.object(llm, "generate", new_callable=AsyncMock, side_effect=Exception("LLM down")):
            result = await llm.verify_recruiter_profiles(
                SAMPLE_PROFILES, "Google", "recruiter"
            )

        assert len(result) == len(SAMPLE_PROFILES)

    async def test_empty_input_returns_empty(self):
        """No profiles → no results, no LLM call."""
        llm = LLMService()
        result = await llm.verify_recruiter_profiles([], "Google", "recruiter")
        assert result == []


class TestRecruiterFinderNoFakes:
    """RecruiterFinderService should NOT generate fake profiles."""

    async def test_find_recruiters_returns_empty(self):
        """Legacy find_recruiters returns empty list — no more fake profiles."""
        finder = RecruiterFinderService()
        result = await finder.find_recruiters(
            company="Google",
            role="Software Engineer",
            user_id=str(uuid.uuid4()),
        )
        assert result == []


class TestRecruiterCompanyFilter:
    """Test company filter on list endpoint."""

    async def test_filter_by_company(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        await factory.create_recruiter(db_session, test_user.id, company="Google", name="Recruiter A")
        await factory.create_recruiter(db_session, test_user.id, company="Microsoft", name="Recruiter B")
        await db_session.commit()

        # Filter by Google
        resp = await client.get("/api/v1/recruiters?company=Google", headers=auth_headers)
        assert resp.status_code == 200
        names = [r["name"] for r in resp.json()["recruiters"]]
        assert "Recruiter A" in names
        assert "Recruiter B" not in names

    async def test_no_filter_returns_all(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        await factory.create_recruiter(db_session, test_user.id, company="Google", name="R1")
        await factory.create_recruiter(db_session, test_user.id, company="Microsoft", name="R2")
        await db_session.commit()

        resp = await client.get("/api/v1/recruiters", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()["recruiters"]) == 2
