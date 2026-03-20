"""
E2E Scenario Tests — Resumes Flow

Tests the complete resume management lifecycle:
1. Create a resume version
2. List all resume versions
3. Get a specific resume
4. Update a resume
5. Delete a resume
6. Get master resume
7. Compile a resume (trigger)
8. Resume tailoring (trigger, returns 202)
9. List templates
10. Full lifecycle: create → update → compile → delete
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

pytestmark = pytest.mark.asyncio

SAMPLE_LATEX = r"""
\documentclass[11pt]{article}
\usepackage[margin=1in]{geometry}
\begin{document}
\section*{John Doe}
\textbf{Software Engineer} \\
john@example.com | (555) 000-0000

\section*{Experience}
\textbf{Senior Backend Engineer} — TechCorp \\
2020--Present
\begin{itemize}
  \item Designed microservices architecture serving 1M+ daily requests
  \item Led migration from monolith to event-driven system
\end{itemize}

\section*{Skills}
Python, FastAPI, PostgreSQL, Docker, Kubernetes, AWS

\end{document}
"""


class TestResumeCreateFlow:
    """Resume creation E2E scenarios."""

    async def test_create_resume_basic(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: Create a new resume version with LaTeX source."""
        response = await client.post(
            "/api/v1/resumes",
            headers=auth_headers,
            json={
                "name": "Master Resume v1",
                "latex_source": SAMPLE_LATEX,
                "is_master": True,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Master Resume v1"
        assert data["is_master"] is True
        assert data["compilation_status"] == "pending"
        assert data["version_number"] == 1

    async def test_create_resume_with_targeting(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: Create resume targeted at specific company/role."""
        response = await client.post(
            "/api/v1/resumes",
            headers=auth_headers,
            json={
                "name": "Google SDE2 Resume",
                "latex_source": SAMPLE_LATEX,
                "target_company": "Google",
                "target_role": "SDE 2",
                "focus_area": "Backend Systems",
                "technologies": ["Python", "Go", "gRPC"],
                "is_master": False,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["target_company"] == "Google"
        assert data["target_role"] == "SDE 2"

    async def test_create_resume_auto_versions(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: Sequential creates get incrementing version numbers."""
        r1 = await client.post(
            "/api/v1/resumes",
            headers=auth_headers,
            json={"name": "v1", "latex_source": SAMPLE_LATEX},
        )
        r2 = await client.post(
            "/api/v1/resumes",
            headers=auth_headers,
            json={"name": "v2", "latex_source": SAMPLE_LATEX},
        )
        assert r1.json()["version_number"] == 1
        assert r2.json()["version_number"] == 2


class TestResumeListFlow:
    """Resume listing E2E scenarios."""

    async def test_list_resumes_empty(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: No resumes → empty list."""
        response = await client.get("/api/v1/resumes", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["resumes"] == []
        assert data["total"] == 0

    async def test_list_resumes_with_data(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """Scenario: Multiple resumes listed correctly."""
        await factory.create_resume(db_session, test_user.id, name="Resume A")
        await factory.create_resume(
            db_session, test_user.id,
            name="Resume B", version_number=2, is_master=False,
        )

        response = await client.get("/api/v1/resumes", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2

    async def test_list_resumes_unauthenticated(self, client: AsyncClient):
        """Scenario: Unauthenticated resume list → 401."""
        response = await client.get("/api/v1/resumes")
        assert response.status_code == 401


class TestResumeDetailFlow:
    """Single resume CRUD E2E scenarios."""

    async def test_get_resume_by_id(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """Scenario: Get a specific resume by UUID."""
        resume = await factory.create_resume(
            db_session, test_user.id, name="Specific Resume"
        )
        response = await client.get(
            f"/api/v1/resumes/{resume.id}", headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Specific Resume"

    async def test_get_nonexistent_resume_returns_404(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: Nonexistent resume UUID → 404."""
        response = await client.get(
            f"/api/v1/resumes/{uuid.uuid4()}", headers=auth_headers
        )
        assert response.status_code == 404

    async def test_update_resume_partial(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """Scenario: PATCH update only changes supplied fields."""
        resume = await factory.create_resume(
            db_session, test_user.id, name="Original Name"
        )
        response = await client.patch(
            f"/api/v1/resumes/{resume.id}",
            headers=auth_headers,
            json={
                "name": "Updated Name",
                "target_company": "Amazon",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["target_company"] == "Amazon"

    async def test_delete_resume(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """Scenario: Delete a resume → 204, then GET → 404."""
        resume = await factory.create_resume(
            db_session, test_user.id, name="To Delete"
        )
        delete_resp = await client.delete(
            f"/api/v1/resumes/{resume.id}", headers=auth_headers
        )
        assert delete_resp.status_code == 204

        # Verify deleted
        get_resp = await client.get(
            f"/api/v1/resumes/{resume.id}", headers=auth_headers
        )
        assert get_resp.status_code == 404


class TestMasterResumeFlow:
    """Master resume E2E scenarios."""

    async def test_get_master_resume(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """Scenario: Get the user's master resume."""
        await factory.create_resume(
            db_session, test_user.id, name="Master", is_master=True
        )
        response = await client.get(
            "/api/v1/resumes/master", headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["is_master"] is True

    async def test_no_master_resume_returns_404(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: No master resume uploaded → 404."""
        response = await client.get(
            "/api/v1/resumes/master", headers=auth_headers
        )
        assert response.status_code == 404


class TestResumeCompileFlow:
    """Resume compilation E2E scenarios."""

    async def test_compile_resume_returns_compiling(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """Scenario: Trigger compilation → returns 'compiling' status."""
        resume = await factory.create_resume(
            db_session, test_user.id, name="To Compile"
        )
        response = await client.post(
            f"/api/v1/resumes/{resume.id}/compile", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "compiling"
        assert data["resume_version_id"] == str(resume.id)


class TestResumeTailorFlow:
    """AI resume tailoring E2E scenarios."""

    async def test_tailor_resume_returns_result(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """Scenario: Request resume tailoring with valid resume+job → success."""
        resume = await factory.create_resume(db_session, test_user.id)
        job = await factory.create_job(db_session, test_user.id)

        with patch("app.api.v1.endpoints.resumes.LLMService") as MockLLM:
            instance = MockLLM.return_value
            instance.tailor_resume = AsyncMock(return_value={
                "tailored_latex": r"\documentclass{article}\begin{document}Tailored\end{document}",
            })
            instance.generate_changes_summary = AsyncMock(return_value={
                "changes_summary": "Added Python keywords",
                "keywords_added": ["Python"],
                "optimization_score": 0.85,
            })
            response = await client.post(
                "/api/v1/resumes/tailor",
                headers=auth_headers,
                json={
                    "base_resume_id": str(resume.id),
                    "job_listing_id": str(job.id),
                    "focus_skills": ["Python", "Microservices"],
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert "changes_summary" in data


class TestResumeTemplateFlow:
    """Resume templates E2E scenarios."""

    async def test_list_templates(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        factory,
    ):
        """Scenario: List available resume templates (no auth required for templates)."""
        await factory.create_resume_template(
            db_session, name="Professional"
        )
        await factory.create_resume_template(
            db_session, name="Academic", category="academic"
        )

        # Note: templates endpoint does not require auth in the code
        response = await client.get("/api/v1/resumes/templates")
        # The endpoint still requires auth because it's under the resumes router
        # but get_current_user_id is not a dependency for list_templates
        assert response.status_code == 200
        templates = response.json()
        assert len(templates) == 2


class TestResumeFullLifecycle:
    """Full resume lifecycle E2E scenario."""

    async def test_create_update_compile_delete(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """
        Full lifecycle:
        1. Create resume
        2. Update content
        3. Trigger compilation
        4. Delete resume
        """
        # Create
        create_resp = await client.post(
            "/api/v1/resumes",
            headers=auth_headers,
            json={
                "name": "Full Lifecycle Resume",
                "latex_source": SAMPLE_LATEX,
                "is_master": True,
            },
        )
        assert create_resp.status_code == 201
        resume_id = create_resp.json()["id"]

        # Update
        update_resp = await client.patch(
            f"/api/v1/resumes/{resume_id}",
            headers=auth_headers,
            json={
                "name": "Updated Lifecycle Resume",
                "target_company": "Netflix",
            },
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["name"] == "Updated Lifecycle Resume"

        # Compile
        compile_resp = await client.post(
            f"/api/v1/resumes/{resume_id}/compile", headers=auth_headers
        )
        assert compile_resp.status_code == 200
        assert compile_resp.json()["status"] == "compiling"

        # Delete
        delete_resp = await client.delete(
            f"/api/v1/resumes/{resume_id}", headers=auth_headers
        )
        assert delete_resp.status_code == 204
