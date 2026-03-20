"""
E2E Scenario Tests â€” LinkedIn Integration & Recruiter/Job Search

Tests LinkedIn-powered features:
1. Find recruiters via LinkedIn (mocked Selenium) â†’ saves real profiles
2. Find recruiters without LinkedIn credentials â†’ returns empty with source="none"
3. LinkedIn job search â†’ saves jobs with description fallback
4. LinkedIn job search deduplication
5. LinkedIn test connection (mocked)
6. LinkedIn inbox fetch (mocked)
7. Recruiter search returns LinkedIn-only (no LLM fallback)
8. Job search handles challenge state
9. ATS Score endpoint (mocked agent)
10. Agents list & status
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import JobSource
from app.models.recruiter import ConnectionStatus
from app.models.user import User

pytestmark = pytest.mark.asyncio

# â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def _mock_linkedin_people_result(company: str, count: int = 3):
    """Build a fake linkedin_search_people return value."""
    return {
        "success": True,
        "connected": True,
        "people": [
            {
                "name": f"Recruiter {i}",
                "title": f"Technical Recruiter at {company}",
                "linkedin_url": f"https://www.linkedin.com/in/recruiter-{i}-{uuid.uuid4().hex[:6]}",
                "location": "San Francisco, CA",
                "company": company,
            }
            for i in range(count)
        ],
        "total_found": count,
        "message": f"Found {count} people at {company}",
    }


def _mock_linkedin_jobs_result(keyword: str, count: int = 5):
    """Build a fake linkedin_search_jobs return value."""
    return {
        "success": True,
        "connected": True,
        "jobs": [
            {
                "title": f"{keyword} Role {i}",
                "company": f"Company{i}",
                "location": "Remote",
                "source_url": f"https://www.linkedin.com/jobs/view/{1000000 + i}/",
                "source_job_id": str(1000000 + i),
                "source": "linkedin",
            }
            for i in range(count)
        ],
        "total_found": count,
        "message": f"Found {count} jobs on LinkedIn",
    }


def _mock_linkedin_empty():
    """LinkedIn search returns empty."""
    return {
        "success": True,
        "connected": True,
        "people": [],
        "jobs": [],
        "total_found": 0,
        "message": "No results found",
    }


def _mock_linkedin_no_creds():
    """LinkedIn search returns no-credentials error."""
    return {
        "success": False,
        "error": "LinkedIn credentials not configured. Add them in Settings.",
        "people": [],
        "jobs": [],
    }


def _mock_linkedin_challenge():
    """LinkedIn search returns challenge state."""
    return {
        "success": False,
        "challenge": True,
        "error": "LinkedIn security challenge detected.",
        "people": [],
        "jobs": [],
    }


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Recruiter Search Tests
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


class TestRecruiterFindLinkedIn:
    """Recruiter discovery via LinkedIn (no LLM fallback)."""

    async def test_find_recruiters_linkedin_success(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: LinkedIn returns recruiters â†’ saves them, source=linkedin."""
        mock_result = _mock_linkedin_people_result("Google", count=3)

        with patch(
            "app.agents.linkedin_helper.linkedin_search_people",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            response = await client.post(
                "/api/v1/recruiters/find",
                headers=auth_headers,
                json={"company": "Google"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "linkedin"
        assert data["total"] == 3
        assert len(data["recruiters"]) == 3
        for r in data["recruiters"]:
            assert "Recruiter" in r["name"]
            assert r["company"] == "Google"
            assert r["connection_status"] == "not_connected"
            assert r["platform"] == "linkedin"
            assert r["linkedin_url"].startswith("https://www.linkedin.com/in/")

    async def test_find_recruiters_linkedin_empty_returns_zero(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: LinkedIn returns 0 people, no LLM fallback â†’ empty list."""
        with patch(
            "app.agents.linkedin_helper.linkedin_search_people",
            new_callable=AsyncMock,
            return_value=_mock_linkedin_empty(),
        ), patch(
            "app.agents.linkedin_helper.get_linkedin_credentials",
            new_callable=AsyncMock,
            return_value={"username": "user@test.com", "password": "pass"},
        ):
            response = await client.post(
                "/api/v1/recruiters/find",
                headers=auth_headers,
                json={"company": "NonexistentCorp"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["recruiters"] == []
        assert data["source"] == "linkedin"

    async def test_find_recruiters_no_linkedin_creds_returns_none_source(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: No LinkedIn creds â†’ source='none', empty list."""
        with patch(
            "app.agents.linkedin_helper.linkedin_search_people",
            new_callable=AsyncMock,
            return_value=_mock_linkedin_no_creds(),
        ), patch(
            "app.agents.linkedin_helper.get_linkedin_credentials",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = await client.post(
                "/api/v1/recruiters/find",
                headers=auth_headers,
                json={"company": "Google"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["source"] == "none"

    async def test_find_recruiters_with_role_filter(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: Role parameter passed through to LinkedIn search."""
        mock_result = _mock_linkedin_people_result("Meta", count=2)

        with patch(
            "app.agents.linkedin_helper.linkedin_search_people",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_search:
            response = await client.post(
                "/api/v1/recruiters/find",
                headers=auth_headers,
                json={"company": "Meta", "role": "engineering manager"},
            )

        assert response.status_code == 200
        assert response.json()["total"] == 2
        # Verify the role was passed
        mock_search.assert_called_once()
        call_args = mock_search.call_args
        assert call_args[1].get("role_keywords") == "engineering manager" or \
               call_args.args[3] == "engineering manager"

    async def test_find_recruiters_deduplicates_by_linkedin_url(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """Scenario: If recruiter already exists by linkedin_url, skip insert."""
        existing_url = "https://www.linkedin.com/in/existing-recruiter"
        await factory.create_recruiter(
            db_session, test_user.id,
            name="Existing Recruiter",
            company="Google",
            linkedin_url=existing_url,
        )

        mock_result = {
            "success": True,
            "people": [
                {
                    "name": "Existing Recruiter",
                    "title": "Recruiter",
                    "linkedin_url": existing_url,
                },
                {
                    "name": "New Recruiter",
                    "title": "Hiring Manager",
                    "linkedin_url": "https://www.linkedin.com/in/new-one",
                },
            ],
            "total_found": 2,
        }

        with patch(
            "app.agents.linkedin_helper.linkedin_search_people",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            response = await client.post(
                "/api/v1/recruiters/find",
                headers=auth_headers,
                json={"company": "Google"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2  # Both returned (1 existing + 1 new)
        names = [r["name"] for r in data["recruiters"]]
        assert "Existing Recruiter" in names
        assert "New Recruiter" in names

    async def test_find_recruiters_unauthenticated(self, client: AsyncClient):
        """Scenario: Unauthenticated find â†’ 401."""
        response = await client.post(
            "/api/v1/recruiters/find",
            json={"company": "Google"},
        )
        assert response.status_code == 401

    async def test_find_recruiters_missing_company_returns_422(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: Missing required company field â†’ 422."""
        response = await client.post(
            "/api/v1/recruiters/find",
            headers=auth_headers,
            json={},
        )
        assert response.status_code == 422

    async def test_find_recruiters_linkedin_exception_handled(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: LinkedIn search throws exception â†’ graceful empty response."""
        with patch(
            "app.agents.linkedin_helper.linkedin_search_people",
            new_callable=AsyncMock,
            side_effect=Exception("Selenium timeout"),
        ), patch(
            "app.agents.linkedin_helper.get_linkedin_credentials",
            new_callable=AsyncMock,
            return_value={"username": "u", "password": "p"},
        ):
            response = await client.post(
                "/api/v1/recruiters/find",
                headers=auth_headers,
                json={"company": "CrashCorp"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["source"] == "linkedin"


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# LinkedIn Job Search Tests
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


class TestLinkedInJobSearch:
    """LinkedIn job search endpoint (POST /jobs/search-linkedin)."""

    async def test_linkedin_job_search_success(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: LinkedIn returns jobs â†’ saved to DB with descriptions."""
        mock_result = _mock_linkedin_jobs_result("Backend Engineer", count=3)

        with patch(
            "app.agents.linkedin_helper.linkedin_search_jobs",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            response = await client.post(
                "/api/v1/jobs/search-linkedin",
                headers=auth_headers,
                json={
                    "filters": {"role": "Backend Engineer", "location": "Remote"},
                    "sources": ["linkedin"],
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "linkedin"
        assert data["saved"] == 3
        assert len(data["jobs"]) == 3
        for job in data["jobs"]:
            assert "Backend Engineer" in job["title"]
            assert job["source"].upper() == "LINKEDIN"

    async def test_linkedin_job_search_deduplicates(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """Scenario: Existing job by source_url is not re-created."""
        existing_url = "https://www.linkedin.com/jobs/view/1000000/"
        await factory.create_job(
            db_session, test_user.id,
            title="Existing Job",
            source_url=existing_url,
        )

        mock_result = {
            "success": True,
            "jobs": [
                {
                    "title": "Existing Job",
                    "company": "OldCo",
                    "source_url": existing_url,
                    "source_job_id": "1000000",
                },
                {
                    "title": "New Job",
                    "company": "NewCo",
                    "source_url": "https://www.linkedin.com/jobs/view/9999999/",
                    "source_job_id": "9999999",
                },
            ],
            "total_found": 2,
        }

        with patch(
            "app.agents.linkedin_helper.linkedin_search_jobs",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            response = await client.post(
                "/api/v1/jobs/search-linkedin",
                headers=auth_headers,
                json={"filters": {"role": "Engineer"}, "sources": ["linkedin"]},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["saved"] == 1  # Only the new one

    async def test_linkedin_job_search_no_keywords_returns_400(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: Empty keywords â†’ 400."""
        response = await client.post(
            "/api/v1/jobs/search-linkedin",
            headers=auth_headers,
            json={"filters": {}, "sources": ["linkedin"]},
        )
        assert response.status_code == 400
        assert "keywords" in response.json()["detail"].lower()

    async def test_linkedin_job_search_no_creds_returns_502(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: No LinkedIn credentials â†’ 502."""
        with patch(
            "app.agents.linkedin_helper.linkedin_search_jobs",
            new_callable=AsyncMock,
            return_value=_mock_linkedin_no_creds(),
        ):
            response = await client.post(
                "/api/v1/jobs/search-linkedin",
                headers=auth_headers,
                json={"filters": {"role": "Engineer"}, "sources": ["linkedin"]},
            )
        assert response.status_code == 502

    async def test_linkedin_job_search_challenge_returns_challenge_field(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: LinkedIn challenge â†’ returns challenge=true, no 500."""
        with patch(
            "app.agents.linkedin_helper.linkedin_search_jobs",
            new_callable=AsyncMock,
            return_value=_mock_linkedin_challenge(),
        ):
            response = await client.post(
                "/api/v1/jobs/search-linkedin",
                headers=auth_headers,
                json={"filters": {"role": "Engineer"}, "sources": ["linkedin"]},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["challenge"] is True
        assert data["jobs"] == []

    async def test_linkedin_job_search_unauthenticated(self, client: AsyncClient):
        """Scenario: Unauthenticated â†’ 401."""
        response = await client.post(
            "/api/v1/jobs/search-linkedin",
            json={"filters": {"role": "Test"}, "sources": ["linkedin"]},
        )
        assert response.status_code == 401

    async def test_linkedin_job_search_results_appear_in_list(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: After LinkedIn search, jobs appear in GET /jobs."""
        mock_result = _mock_linkedin_jobs_result("SDE", count=2)

        with patch(
            "app.agents.linkedin_helper.linkedin_search_jobs",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            await client.post(
                "/api/v1/jobs/search-linkedin",
                headers=auth_headers,
                json={"filters": {"role": "SDE"}, "sources": ["linkedin"]},
            )

        # Now list should have them
        list_resp = await client.get("/api/v1/jobs", headers=auth_headers)
        assert list_resp.status_code == 200
        assert list_resp.json()["total"] == 2


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# LinkedIn Connection Test & Inbox
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


class TestLinkedInConnection:
    """LinkedIn test connection and inbox endpoints."""

    async def test_linkedin_test_no_creds_returns_400(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: No LinkedIn creds saved â†’ 400."""
        response = await client.get(
            "/api/v1/recruiters/linkedin/test",
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "credentials" in response.json()["detail"].lower()

    async def test_linkedin_inbox_no_creds_returns_400(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: No LinkedIn creds saved â†’ 400."""
        response = await client.get(
            "/api/v1/recruiters/linkedin/inbox",
            headers=auth_headers,
        )
        assert response.status_code == 400

    async def test_linkedin_test_unauthenticated(self, client: AsyncClient):
        """Scenario: Unauthenticated â†’ 401."""
        response = await client.get("/api/v1/recruiters/linkedin/test")
        assert response.status_code == 401

    async def test_linkedin_inbox_unauthenticated(self, client: AsyncClient):
        """Scenario: Unauthenticated â†’ 401."""
        response = await client.get("/api/v1/recruiters/linkedin/inbox")
        assert response.status_code == 401


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# ATS Score Endpoint Tests
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


class TestATSScore:
    """ATS resume scoring endpoint."""

    async def test_ats_score_success(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """Scenario: ATS score with resume + job â†’ returns score breakdown."""
        from app.agents.base import AgentResult

        resume = await factory.create_resume(db_session, test_user.id)
        job = await factory.create_job(db_session, test_user.id)

        mock_result = AgentResult(
            success=True,
            data={
                "overall_score": 75,
                "breakdown": {
                    "keyword_match": 80,
                    "formatting": 90,
                    "experience_relevance": 70,
                    "skills_alignment": 65,
                    "education_fit": 75,
                    "quantification": 60,
                },
                "matched_keywords": ["Python", "FastAPI", "PostgreSQL"],
                "missing_keywords": ["Kubernetes", "Terraform"],
                "strengths": ["Strong backend experience"],
                "weaknesses": ["Missing cloud skills"],
                "suggestions": ["Add Kubernetes experience"],
                "summary": "Good match with room for improvement",
            },
        )

        with patch(
            "app.agents.ats_scoring_agent.ATSScoringAgent"
        ) as MockAgent:
            instance = MockAgent.return_value
            instance.run = AsyncMock(return_value=mock_result)

            response = await client.post(
                "/api/v1/resumes/ats-score",
                headers=auth_headers,
                json={
                    "resume_id": str(resume.id),
                    "job_id": str(job.id),
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["overall_score"] == 75
        assert "keyword_match" in data["breakdown"]
        assert data["breakdown"]["keyword_match"] == 80
        assert "Python" in data["matched_keywords"]
        assert "Kubernetes" in data["missing_keywords"]
        assert len(data["strengths"]) == 1
        assert len(data["suggestions"]) == 1

    async def test_ats_score_with_custom_jd(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: ATS score with pasted JD text."""
        from app.agents.base import AgentResult

        mock_result = AgentResult(
            success=True,
            data={"overall_score": 60, "breakdown": {}, "matched_keywords": [],
                  "missing_keywords": [], "strengths": [], "weaknesses": [],
                  "suggestions": [], "summary": "Average match"},
        )

        with patch(
            "app.agents.ats_scoring_agent.ATSScoringAgent"
        ) as MockAgent:
            instance = MockAgent.return_value
            instance.run = AsyncMock(return_value=mock_result)

            response = await client.post(
                "/api/v1/resumes/ats-score",
                headers=auth_headers,
                json={
                    "job_description": "We are looking for a Python developer with 5+ years experience...",
                },
            )

        assert response.status_code == 200
        assert response.json()["overall_score"] == 60

    async def test_ats_score_agent_failure_returns_422(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: ATS agent fails â†’ 422."""
        from app.agents.base import AgentResult

        mock_result = AgentResult(
            success=False,
            errors=["No resume content found"],
        )

        with patch(
            "app.agents.ats_scoring_agent.ATSScoringAgent"
        ) as MockAgent:
            instance = MockAgent.return_value
            instance.run = AsyncMock(return_value=mock_result)

            response = await client.post(
                "/api/v1/resumes/ats-score",
                headers=auth_headers,
                json={"job_description": "Test JD"},
            )

        assert response.status_code == 422
        assert "resume content" in response.json()["detail"].lower()

    async def test_ats_score_unauthenticated(self, client: AsyncClient):
        """Scenario: Unauthenticated â†’ 401."""
        response = await client.post(
            "/api/v1/resumes/ats-score",
            json={"job_description": "Test JD"},
        )
        assert response.status_code == 401


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Agent Endpoints Tests
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


class TestAgentsEndpoints:
    """Agent management endpoints."""

    async def test_list_agents(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: GET /agents lists all registered agents."""
        response = await client.get("/api/v1/agents", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        agents = data.get("agents", data) if isinstance(data, dict) else data
        assert isinstance(agents, list)
        assert len(agents) > 0
        # Check agent shape
        agent = agents[0]
        assert "name" in agent
        assert "enabled" in agent

    async def test_agents_status(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: GET /agents/status returns per-agent status."""
        response = await client.get("/api/v1/agents/status", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        # Status returns either a dict with 'agents' key or a list
        assert isinstance(data, (dict, list))
        if isinstance(data, dict):
            assert "agents" in data or "total" in data

    async def test_agents_history(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: GET /agents/history returns empty initially."""
        response = await client.get("/api/v1/agents/history", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list) or isinstance(data, dict)

    async def test_agents_unauthenticated(self, client: AsyncClient):
        """Scenario: Unauthenticated agents list â†’ 401."""
        response = await client.get("/api/v1/agents")
        assert response.status_code == 401

    async def test_run_nonexistent_agent_returns_404(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: Run unknown agent name â†’ 404."""
        response = await client.post(
            "/api/v1/agents/nonexistent_agent_xyz/run",
            headers=auth_headers,
            json={},
        )
        assert response.status_code == 404


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Outreach Messages Full Flow
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


class TestOutreachMessagesListAll:
    """Global outreach messages endpoint."""

    async def test_list_all_messages_empty(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: No messages â†’ empty list."""
        response = await client.get(
            "/api/v1/recruiters/messages/all", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["messages"] == []
        assert data["total"] == 0

    async def test_list_all_messages_with_data(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """Scenario: Messages exist â†’ returns with recruiter details."""
        recruiter = await factory.create_recruiter(
            db_session, test_user.id,
            name="Msg Target",
            company="TestCo",
        )
        await factory.create_outreach_message(
            db_session, test_user.id, recruiter.id,
            body="Hello there!",
        )

        response = await client.get(
            "/api/v1/recruiters/messages/all", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        msg = data["messages"][0]
        assert msg["recruiter_name"] == "Msg Target"
        assert msg["body"] == "Hello there!"


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Recruiter Get Messages for Specific Recruiter
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


class TestRecruiterMessages:
    """Per-recruiter message retrieval."""

    async def test_get_messages_for_recruiter(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """Scenario: Get messages for specific recruiter."""
        recruiter = await factory.create_recruiter(
            db_session, test_user.id, name="Msg Recruiter"
        )
        await factory.create_outreach_message(
            db_session, test_user.id, recruiter.id,
            body="Message 1",
        )
        await factory.create_outreach_message(
            db_session, test_user.id, recruiter.id,
            body="Message 2",
        )

        response = await client.get(
            f"/api/v1/recruiters/{recruiter.id}/messages",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    async def test_get_messages_nonexistent_recruiter(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: Messages for nonexistent recruiter â†’ empty list (not 404)."""
        response = await client.get(
            f"/api/v1/recruiters/{uuid.uuid4()}/messages",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert len(response.json()) == 0


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Full Cross-Flow: LinkedIn Search â†’ List â†’ Detail
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


class TestCrossFlowLinkedIn:
    """Full lifecycle integration tests."""

    async def test_search_recruiters_then_list_and_get_detail(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Full flow: find via LinkedIn â†’ appears in list â†’ get by ID."""
        mock_result = _mock_linkedin_people_result("Stripe", count=2)

        with patch(
            "app.agents.linkedin_helper.linkedin_search_people",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            find_resp = await client.post(
                "/api/v1/recruiters/find",
                headers=auth_headers,
                json={"company": "Stripe"},
            )

        assert find_resp.status_code == 200
        recruiter_id = find_resp.json()["recruiters"][0]["id"]

        # List should contain them
        list_resp = await client.get("/api/v1/recruiters", headers=auth_headers)
        assert list_resp.json()["total"] == 2

        # Detail should work
        detail_resp = await client.get(
            f"/api/v1/recruiters/{recruiter_id}", headers=auth_headers
        )
        assert detail_resp.status_code == 200
        assert detail_resp.json()["company"] == "Stripe"

    async def test_search_jobs_then_list_and_get_detail(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Full flow: LinkedIn job search â†’ appears in list â†’ get by ID."""
        mock_result = _mock_linkedin_jobs_result("DevOps", count=2)

        with patch(
            "app.agents.linkedin_helper.linkedin_search_jobs",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            search_resp = await client.post(
                "/api/v1/jobs/search-linkedin",
                headers=auth_headers,
                json={"filters": {"role": "DevOps"}, "sources": ["linkedin"]},
            )

        assert search_resp.status_code == 200
        job_id = search_resp.json()["jobs"][0]["id"]

        # List
        list_resp = await client.get("/api/v1/jobs", headers=auth_headers)
        assert list_resp.json()["total"] == 2

        # Detail
        detail_resp = await client.get(
            f"/api/v1/jobs/{job_id}", headers=auth_headers
        )
        assert detail_resp.status_code == 200
        assert "DevOps" in detail_resp.json()["title"]

    async def test_full_resume_ats_flow(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Full flow: create resume â†’ create job â†’ ATS score."""
        from app.agents.base import AgentResult

        # Create resume
        resume_resp = await client.post(
            "/api/v1/resumes",
            headers=auth_headers,
            json={
                "name": "Test Resume",
                "latex_source": r"\documentclass{article}\begin{document}Test\end{document}",
                "is_master": True,
            },
        )
        assert resume_resp.status_code == 201
        resume_id = resume_resp.json()["id"]

        # ATS Score
        mock_result = AgentResult(
            success=True,
            data={"overall_score": 82, "breakdown": {}, "matched_keywords": ["Python"],
                  "missing_keywords": [], "strengths": ["Good"], "weaknesses": [],
                  "suggestions": [], "summary": "Great match"},
        )

        with patch(
            "app.agents.ats_scoring_agent.ATSScoringAgent"
        ) as MockAgent:
            instance = MockAgent.return_value
            instance.run = AsyncMock(return_value=mock_result)

            ats_resp = await client.post(
                "/api/v1/resumes/ats-score",
                headers=auth_headers,
                json={
                    "resume_id": resume_id,
                    "job_description": "Looking for Python experts",
                },
            )

        assert ats_resp.status_code == 200
        assert ats_resp.json()["overall_score"] == 82
