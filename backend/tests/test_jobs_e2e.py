"""
E2E Scenario Tests — Jobs Flow

Tests the complete job discovery and management lifecycle:
1. List jobs (empty initially)
2. Create jobs via demo data → list returns them
3. Get single job by ID
4. Top matches (sorted by score)
5. Trigger job search (async, returns 202)
6. Get match score for a job
7. Pagination works correctly
8. Filter by source / company
9. Unauthenticated access → 401
10. Non-existent job → 404
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import JobSource
from app.models.user import User

pytestmark = pytest.mark.asyncio


class TestJobListFlow:
    """Job listing and pagination E2E scenarios."""

    async def test_list_jobs_empty(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: No jobs yet → returns empty list."""
        response = await client.get("/api/v1/jobs", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["jobs"] == []
        assert data["total"] == 0

    async def test_list_jobs_with_data(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """Scenario: Jobs exist → returns paginated list."""
        # Create 3 jobs
        for i in range(3):
            await factory.create_job(
                db_session,
                test_user.id,
                title=f"Engineer {i}",
                company=f"Company{i}",
                source_url=f"https://example.com/job{i}",
            )

        response = await client.get("/api/v1/jobs", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["jobs"]) == 3

    async def test_list_jobs_pagination(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """Scenario: Pagination returns correct page slices."""
        for i in range(5):
            await factory.create_job(
                db_session,
                test_user.id,
                title=f"Job {i}",
                source_url=f"https://example.com/paginate{i}",
            )

        # Page 1, size 2
        r1 = await client.get(
            "/api/v1/jobs?page=1&page_size=2", headers=auth_headers
        )
        assert r1.status_code == 200
        assert len(r1.json()["jobs"]) == 2
        assert r1.json()["total"] == 5

        # Page 3, size 2 → 1 remaining job
        r3 = await client.get(
            "/api/v1/jobs?page=3&page_size=2", headers=auth_headers
        )
        assert r3.status_code == 200
        assert len(r3.json()["jobs"]) == 1

    async def test_list_jobs_filter_by_company(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """Scenario: Filter jobs by company name."""
        await factory.create_job(
            db_session, test_user.id, company="Google",
            source_url="https://example.com/google1",
        )
        await factory.create_job(
            db_session, test_user.id, company="Meta",
            source_url="https://example.com/meta1",
        )

        response = await client.get(
            "/api/v1/jobs?company=Google", headers=auth_headers
        )
        assert response.status_code == 200
        jobs = response.json()["jobs"]
        assert len(jobs) == 1
        assert jobs[0]["company"] == "Google"

    async def test_list_jobs_unauthenticated(self, client: AsyncClient):
        """Scenario: Unauthenticated job list → 401."""
        response = await client.get("/api/v1/jobs")
        assert response.status_code == 401


class TestJobDetailFlow:
    """Single job retrieval E2E scenarios."""

    async def test_get_job_by_id(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """Scenario: Get a specific job by UUID."""
        job = await factory.create_job(
            db_session, test_user.id, title="Python Backend Dev"
        )
        response = await client.get(
            f"/api/v1/jobs/{job.id}", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Python Backend Dev"
        assert data["company"] == "TechCorp"

    async def test_get_nonexistent_job_returns_404(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: Nonexistent job UUID → 404."""
        fake_id = str(uuid.uuid4())
        response = await client.get(
            f"/api/v1/jobs/{fake_id}", headers=auth_headers
        )
        assert response.status_code == 404


class TestTopMatchesFlow:
    """AI match score E2E scenarios."""

    async def test_top_matches_sorted_by_score(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """Scenario: Top matches returns jobs sorted by match_score desc."""
        await factory.create_job(
            db_session, test_user.id,
            title="Low Match", match_score=0.3,
            source_url="https://example.com/low",
        )
        await factory.create_job(
            db_session, test_user.id,
            title="High Match", match_score=0.95,
            source_url="https://example.com/high",
        )
        await factory.create_job(
            db_session, test_user.id,
            title="Mid Match", match_score=0.7,
            source_url="https://example.com/mid",
        )

        response = await client.get(
            "/api/v1/jobs/top-matches?min_score=0.5", headers=auth_headers
        )
        assert response.status_code == 200
        jobs = response.json()
        assert len(jobs) == 2  # Only 0.95 and 0.7 pass threshold
        assert jobs[0]["title"] == "High Match"
        assert jobs[1]["title"] == "Mid Match"

    async def test_top_matches_min_score_filter(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """Scenario: min_score=0.9 filters out lower matches."""
        await factory.create_job(
            db_session, test_user.id,
            title="Almost", match_score=0.89,
            source_url="https://example.com/almost",
        )
        await factory.create_job(
            db_session, test_user.id,
            title="Perfect", match_score=0.95,
            source_url="https://example.com/perfect",
        )

        response = await client.get(
            "/api/v1/jobs/top-matches?min_score=0.9", headers=auth_headers
        )
        assert response.status_code == 200
        jobs = response.json()
        assert len(jobs) == 1
        assert jobs[0]["title"] == "Perfect"


class TestJobSearchFlow:
    """Job search trigger E2E scenarios."""

    async def test_trigger_job_search(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: Trigger async job search → returns 202."""
        response = await client.post(
            "/api/v1/jobs/search",
            headers=auth_headers,
            json={
                "filters": {
                    "role": "Backend Engineer",
                    "technologies": ["Python", "FastAPI"],
                    "location": "Remote",
                },
                "sources": ["linkedin", "indeed"],
            },
        )
        assert response.status_code == 202
        data = response.json()
        assert data["message"] == "Job search initiated"
        assert "linkedin" in data["sources"]
        assert "indeed" in data["sources"]


class TestJobMatchScoreFlow:
    """Match score retrieval E2E scenarios."""

    async def test_get_match_score_for_job(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """Scenario: Get AI match score for a specific job."""
        job = await factory.create_job(
            db_session, test_user.id,
            match_score=0.87,
        )
        response = await client.get(
            f"/api/v1/jobs/{job.id}/match-score", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["match_score"] == 0.87
        assert "reasoning" in data

    async def test_match_score_nonexistent_job(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: Match score for nonexistent job → 404."""
        response = await client.get(
            f"/api/v1/jobs/{uuid.uuid4()}/match-score", headers=auth_headers
        )
        assert response.status_code == 404
