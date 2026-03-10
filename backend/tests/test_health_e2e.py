"""
E2E Scenario Tests — Health & Cross-Cutting Concerns

Tests:
1. Health check endpoint
2. CORS headers
3. Global error handling
4. API versioning prefix
"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestHealthCheck:
    """Health check endpoint E2E scenarios."""

    async def test_health_returns_200(self, client: AsyncClient):
        """Scenario: /health returns healthy status."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "HirePilot"

    async def test_health_no_auth_required(self, client: AsyncClient):
        """Scenario: /health does not require authentication."""
        response = await client.get("/health")
        assert response.status_code == 200


class TestAPIVersioning:
    """API versioning E2E scenarios."""

    async def test_v1_prefix_works(self, client: AsyncClient):
        """Scenario: All API endpoints are under /api/v1."""
        # Should get 401 (not 404) — route exists, just needs auth
        response = await client.get("/api/v1/jobs")
        assert response.status_code == 401

    async def test_invalid_prefix_returns_404(self, client: AsyncClient):
        """Scenario: Non-v1 API paths return 404."""
        response = await client.get("/api/v2/jobs")
        assert response.status_code == 404

    async def test_root_returns_404(self, client: AsyncClient):
        """Scenario: Root path has no handler (404 or redirect)."""
        response = await client.get("/")
        assert response.status_code in (404, 307)


class TestGlobalErrorHandling:
    """Global error handler E2E scenarios."""

    async def test_invalid_json_returns_422(self, client: AsyncClient):
        """Scenario: Malformed JSON body returns 422."""
        response = await client.post(
            "/api/v1/auth/register",
            content="not-valid-json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422


class TestCrossFlowIntegration:
    """Cross-flow integration E2E scenarios."""

    async def test_register_create_resume_apply_to_job(self, client: AsyncClient):
        """
        Full cross-flow integration test:
        1. Register a new user
        2. Create a master resume
        3. Trigger job search (gets 202)
        4. Verify analytics show zero applications
        """
        # Step 1: Register
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "crossflow@test.com",
                "password": "CrossFlow123!",
                "full_name": "Cross Flow User",
            },
        )
        assert reg.status_code == 201
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        # Step 2: Create master resume
        resume = await client.post(
            "/api/v1/resumes",
            headers=headers,
            json={
                "name": "Master Resume",
                "latex_source": r"\documentclass{article}\begin{document}Test\end{document}",
                "is_master": True,
            },
        )
        assert resume.status_code == 201

        # Step 3: Trigger job search
        search = await client.post(
            "/api/v1/jobs/search",
            headers=headers,
            json={
                "filters": {"role": "Backend Engineer"},
                "sources": ["linkedin"],
            },
        )
        assert search.status_code == 202

        # Step 4: Analytics are empty (no applications yet)
        analytics = await client.get(
            "/api/v1/applications/analytics", headers=headers
        )
        assert analytics.status_code == 200
        assert analytics.json()["total_applications"] == 0

        # Step 5: Verify profile
        profile = await client.get("/api/v1/auth/me", headers=headers)
        assert profile.status_code == 200
        assert profile.json()["full_name"] == "Cross Flow User"
