"""
E2E Scenario Tests — Applications Flow

Tests the complete application management lifecycle:
1. Create an application (requires job + resume)
2. List applications with filters
3. Update application status (draft → applied → interview → offer)
4. Prevent duplicate applications to same job
5. Auto-apply trigger (returns 202)
6. Analytics endpoint
7. Full lifecycle: create → status transitions → analytics
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import ApplicationStatus
from app.models.user import User

pytestmark = pytest.mark.asyncio


class TestApplicationCreateFlow:
    """Application creation E2E scenarios."""

    async def test_create_application_with_existing_job_and_resume(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """Scenario: Create an application linking to existing job + resume."""
        job = await factory.create_job(db_session, test_user.id)
        resume = await factory.create_resume(db_session, test_user.id)

        response = await client.post(
            "/api/v1/applications",
            headers=auth_headers,
            json={
                "job_listing_id": str(job.id),
                "resume_version_id": str(resume.id),
                "cover_letter": "I am excited to apply...",
                "notes": "Applied via referral",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["company"] == "TechCorp"
        assert data["role"] == "Senior Backend Engineer"
        assert data["status"] == "draft"
        assert data["cover_letter"] == "I am excited to apply..."

    async def test_create_application_nonexistent_job_returns_400(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """Scenario: Application for nonexistent job → 400."""
        resume = await factory.create_resume(db_session, test_user.id)

        response = await client.post(
            "/api/v1/applications",
            headers=auth_headers,
            json={
                "job_listing_id": str(uuid.uuid4()),
                "resume_version_id": str(resume.id),
            },
        )
        assert response.status_code == 400
        assert "not found" in response.json()["detail"].lower()

    async def test_create_duplicate_application_returns_400(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """Scenario: Cannot apply twice to the same job."""
        job = await factory.create_job(db_session, test_user.id)
        resume = await factory.create_resume(db_session, test_user.id)

        # First application succeeds
        r1 = await client.post(
            "/api/v1/applications",
            headers=auth_headers,
            json={
                "job_listing_id": str(job.id),
                "resume_version_id": str(resume.id),
            },
        )
        assert r1.status_code == 201

        # Second application fails
        r2 = await client.post(
            "/api/v1/applications",
            headers=auth_headers,
            json={
                "job_listing_id": str(job.id),
                "resume_version_id": str(resume.id),
            },
        )
        assert r2.status_code == 400
        assert "already applied" in r2.json()["detail"].lower()

    async def test_create_application_unauthenticated(self, client: AsyncClient):
        """Scenario: Unauthenticated application creation → 401."""
        response = await client.post(
            "/api/v1/applications",
            json={
                "job_listing_id": str(uuid.uuid4()),
                "resume_version_id": str(uuid.uuid4()),
            },
        )
        assert response.status_code == 401


class TestApplicationListFlow:
    """Application listing E2E scenarios."""

    async def test_list_applications_empty(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: No applications → empty list."""
        response = await client.get("/api/v1/applications", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["applications"] == []
        assert data["total"] == 0

    async def test_list_applications_with_data(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """Scenario: Applications exist → returns paginated list."""
        job1 = await factory.create_job(
            db_session, test_user.id,
            company="Google",
            source_url="https://example.com/g1",
        )
        job2 = await factory.create_job(
            db_session, test_user.id,
            company="Meta",
            source_url="https://example.com/m1",
        )
        resume = await factory.create_resume(db_session, test_user.id)

        await factory.create_application(
            db_session, test_user.id, job1.id, resume.id,
            company="Google", role="SDE 2",
        )
        await factory.create_application(
            db_session, test_user.id, job2.id, resume.id,
            company="Meta", role="Senior Engineer",
        )

        response = await client.get("/api/v1/applications", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["applications"]) == 2

    async def test_list_applications_filter_by_status(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """Scenario: Filter applications by status."""
        job1 = await factory.create_job(
            db_session, test_user.id,
            source_url="https://example.com/filter1",
        )
        job2 = await factory.create_job(
            db_session, test_user.id,
            source_url="https://example.com/filter2",
        )
        resume = await factory.create_resume(db_session, test_user.id)

        await factory.create_application(
            db_session, test_user.id, job1.id, resume.id,
            status=ApplicationStatus.DRAFT,
        )
        await factory.create_application(
            db_session, test_user.id, job2.id, resume.id,
            status=ApplicationStatus.APPLIED,
        )

        response = await client.get(
            "/api/v1/applications?status=applied", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["applications"][0]["status"] == "applied"


class TestApplicationStatusFlow:
    """Application status transition E2E scenarios."""

    async def test_update_status_draft_to_applied(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """Scenario: Transition status from draft → applied."""
        job = await factory.create_job(db_session, test_user.id)
        resume = await factory.create_resume(db_session, test_user.id)
        app = await factory.create_application(
            db_session, test_user.id, job.id, resume.id,
            status=ApplicationStatus.DRAFT,
        )

        response = await client.patch(
            f"/api/v1/applications/{app.id}/status",
            headers=auth_headers,
            json={"status": "applied", "notes": "Submitted via LinkedIn"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "applied"
        assert data["applied_date"] is not None

    async def test_status_pipeline_full_flow(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """Scenario: Full status pipeline: draft → applied → interview → offer."""
        job = await factory.create_job(db_session, test_user.id)
        resume = await factory.create_resume(db_session, test_user.id)
        app = await factory.create_application(
            db_session, test_user.id, job.id, resume.id,
        )

        # draft → applied
        r1 = await client.patch(
            f"/api/v1/applications/{app.id}/status",
            headers=auth_headers,
            json={"status": "applied"},
        )
        assert r1.status_code == 200
        assert r1.json()["status"] == "applied"

        # applied → interview
        r2 = await client.patch(
            f"/api/v1/applications/{app.id}/status",
            headers=auth_headers,
            json={"status": "interview", "notes": "Technical round scheduled"},
        )
        assert r2.status_code == 200
        assert r2.json()["status"] == "interview"
        assert r2.json()["response_date"] is not None

        # interview → offer
        r3 = await client.patch(
            f"/api/v1/applications/{app.id}/status",
            headers=auth_headers,
            json={"status": "offer", "notes": "Got the offer! 🎉"},
        )
        assert r3.status_code == 200
        assert r3.json()["status"] == "offer"

    async def test_update_nonexistent_application_returns_400(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: Status update on nonexistent application → 400."""
        response = await client.patch(
            f"/api/v1/applications/{uuid.uuid4()}/status",
            headers=auth_headers,
            json={"status": "applied"},
        )
        assert response.status_code == 400


class TestAutoApplyFlow:
    """Automated application E2E scenarios."""

    async def test_auto_apply_returns_202(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: Auto-apply trigger → 202 accepted."""
        app_id = str(uuid.uuid4())
        response = await client.post(
            f"/api/v1/applications/{app_id}/apply",
            headers=auth_headers,
            json={
                "job_listing_id": str(uuid.uuid4()),
                "resume_version_id": str(uuid.uuid4()),
            },
        )
        assert response.status_code == 202
        data = response.json()
        assert data["message"] == "Auto-apply task queued"
        assert data["application_id"] == app_id


class TestApplicationAnalyticsFlow:
    """Application analytics E2E scenarios."""

    async def test_analytics_empty(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: No applications → zero-ed analytics."""
        response = await client.get(
            "/api/v1/applications/analytics", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_applications"] == 0
        assert data["response_rate"] == 0.0
        assert data["interview_rate"] == 0.0

    async def test_analytics_with_data(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """Scenario: Analytics compute rates from application data."""
        resume = await factory.create_resume(db_session, test_user.id)

        # Create 4 applications with different statuses
        statuses = [
            ApplicationStatus.APPLIED,
            ApplicationStatus.INTERVIEW,
            ApplicationStatus.REJECTED,
            ApplicationStatus.DRAFT,
        ]
        for i, status in enumerate(statuses):
            job = await factory.create_job(
                db_session, test_user.id,
                title=f"Job {i}",
                source_url=f"https://example.com/analytics{i}",
            )
            await factory.create_application(
                db_session, test_user.id, job.id, resume.id,
                company=f"Co{i}", role=f"Role{i}", status=status,
            )

        response = await client.get(
            "/api/v1/applications/analytics", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_applications"] == 4
        # Interview (1) + Rejected (1) = 2 responses out of 4
        assert data["response_rate"] == 0.5
        # Interview (1) out of 4
        assert data["interview_rate"] == 0.25


class TestApplicationFullLifecycle:
    """Full application lifecycle E2E scenario."""

    async def test_full_application_journey(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """
        Full lifecycle:
        1. Create job and resume (prerequisites)
        2. Create application
        3. Update status: draft → applied → interview → offer
        4. Verify analytics reflect the journey
        """
        # Prerequisites
        job = await factory.create_job(
            db_session, test_user.id,
            title="Dream Job", company="DreamCorp",
        )
        resume = await factory.create_resume(db_session, test_user.id)

        # Create application
        create_resp = await client.post(
            "/api/v1/applications",
            headers=auth_headers,
            json={
                "job_listing_id": str(job.id),
                "resume_version_id": str(resume.id),
                "cover_letter": "My passion for this role...",
            },
        )
        assert create_resp.status_code == 201
        app_id = create_resp.json()["id"]

        # Status: draft → applied
        await client.patch(
            f"/api/v1/applications/{app_id}/status",
            headers=auth_headers,
            json={"status": "applied"},
        )

        # Status: applied → interview
        await client.patch(
            f"/api/v1/applications/{app_id}/status",
            headers=auth_headers,
            json={"status": "interview", "notes": "Phone screen passed"},
        )

        # Status: interview → offer
        offer_resp = await client.patch(
            f"/api/v1/applications/{app_id}/status",
            headers=auth_headers,
            json={"status": "offer", "notes": "$180K base + equity"},
        )
        assert offer_resp.status_code == 200
        assert offer_resp.json()["status"] == "offer"

        # Check analytics
        analytics = await client.get(
            "/api/v1/applications/analytics", headers=auth_headers
        )
        assert analytics.status_code == 200
        a_data = analytics.json()
        assert a_data["total_applications"] == 1
        assert a_data["interview_rate"] == 1.0


class TestWizardApplyRouteOrdering:
    """
    Regression tests for route ordering bug:
    POST /wizard/apply was being intercepted by /{application_id}/apply
    because the dynamic route was defined first, causing 422 errors.
    """

    async def test_wizard_apply_route_not_hijacked_by_dynamic_route(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ):
        """
        POST /wizard/apply with WizardAutoApplyRequest body must NOT
        be matched by /{application_id}/apply (which expects AutoApplyRequest).
        A 422 here means the dynamic route intercepted the request.
        """
        app_id = str(uuid.uuid4())
        response = await client.post(
            "/api/v1/applications/wizard/apply",
            headers=auth_headers,
            json={"application_id": app_id},
        )
        # Must NOT be 422 — that would mean the wrong route matched
        assert response.status_code != 422, (
            "wizard/apply was intercepted by /{application_id}/apply route; "
            "check that /wizard/apply is defined BEFORE dynamic path routes"
        )
        # The endpoint should be reached (200 from the wizard handler).
        # It may fail with a Celery error in test, but the route itself is hit.
        assert response.status_code == 200
        data = response.json()
        assert data["application_id"] == app_id
        assert "task_id" in data
        assert data["step"] == "applying"

    async def test_legacy_auto_apply_still_works(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ):
        """Legacy /{application_id}/apply endpoint still functions after reorder."""
        app_id = str(uuid.uuid4())
        response = await client.post(
            f"/api/v1/applications/{app_id}/apply",
            headers=auth_headers,
            json={
                "job_listing_id": str(uuid.uuid4()),
                "resume_version_id": str(uuid.uuid4()),
            },
        )
        assert response.status_code == 202
        data = response.json()
        assert data["application_id"] == app_id
        assert data["message"] == "Auto-apply task queued"

    async def test_wizard_apply_unauthenticated_returns_401(
        self,
        client: AsyncClient,
    ):
        """POST /wizard/apply without auth token → 401, not 422."""
        response = await client.post(
            "/api/v1/applications/wizard/apply",
            json={"application_id": str(uuid.uuid4())},
        )
        assert response.status_code == 401
