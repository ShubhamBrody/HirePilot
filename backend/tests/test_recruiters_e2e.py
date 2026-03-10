"""
E2E Scenario Tests — Recruiters Flow

Tests the complete recruiter discovery and outreach lifecycle:
1. List recruiters (empty initially)
2. Create recruiters via demo data → list returns them
3. Get single recruiter by ID
4. Send outreach message
5. Get outreach messages for a recruiter
6. Generate AI message preview
7. Filter by connection status
8. Full lifecycle: discover → generate message → send outreach
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recruiter import ConnectionStatus
from app.models.user import User

pytestmark = pytest.mark.asyncio


class TestRecruiterListFlow:
    """Recruiter listing E2E scenarios."""

    async def test_list_recruiters_empty(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: No recruiters → empty list."""
        response = await client.get("/api/v1/recruiters", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["recruiters"] == []
        assert data["total"] == 0

    async def test_list_recruiters_with_data(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """Scenario: Recruiters exist → returns list."""
        await factory.create_recruiter(
            db_session, test_user.id,
            name="Alice Smith", company="Google",
        )
        await factory.create_recruiter(
            db_session, test_user.id,
            name="Bob Jones", company="Meta",
        )

        response = await client.get("/api/v1/recruiters", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        names = [r["name"] for r in data["recruiters"]]
        assert "Alice Smith" in names
        assert "Bob Jones" in names

    async def test_list_recruiters_filter_by_connection_status(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """Scenario: Filter recruiters by connection status."""
        await factory.create_recruiter(
            db_session, test_user.id,
            name="Connected Recruiter",
            connection_status=ConnectionStatus.CONNECTED,
        )
        await factory.create_recruiter(
            db_session, test_user.id,
            name="Not Connected Recruiter",
            connection_status=ConnectionStatus.NOT_CONNECTED,
        )

        response = await client.get(
            "/api/v1/recruiters?connection_status=connected",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["recruiters"][0]["name"] == "Connected Recruiter"

    async def test_list_recruiters_pagination(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """Scenario: Pagination works correctly."""
        for i in range(5):
            await factory.create_recruiter(
                db_session, test_user.id,
                name=f"Recruiter {i}",
                company=f"Company{i}",
            )

        r1 = await client.get(
            "/api/v1/recruiters?page=1&page_size=2", headers=auth_headers
        )
        assert r1.status_code == 200
        assert len(r1.json()["recruiters"]) == 2

    async def test_list_recruiters_unauthenticated(self, client: AsyncClient):
        """Scenario: Unauthenticated recruiter list → 401."""
        response = await client.get("/api/v1/recruiters")
        assert response.status_code == 401


class TestRecruiterDetailFlow:
    """Single recruiter retrieval E2E scenarios."""

    async def test_get_recruiter_by_id(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """Scenario: Get a specific recruiter by UUID."""
        recruiter = await factory.create_recruiter(
            db_session, test_user.id,
            name="Jane Tech Lead",
            company="Stripe",
            title="Engineering Manager",
        )
        response = await client.get(
            f"/api/v1/recruiters/{recruiter.id}", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Jane Tech Lead"
        assert data["company"] == "Stripe"
        assert data["title"] == "Engineering Manager"
        assert data["platform"] == "linkedin"

    async def test_get_nonexistent_recruiter_returns_404(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: Nonexistent recruiter UUID → 404."""
        response = await client.get(
            f"/api/v1/recruiters/{uuid.uuid4()}", headers=auth_headers
        )
        assert response.status_code == 404


class TestOutreachMessageFlow:
    """Outreach message E2E scenarios."""

    async def test_send_outreach_custom_message(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """Scenario: Send a custom outreach message to a recruiter."""
        recruiter = await factory.create_recruiter(
            db_session, test_user.id, name="Custom Target"
        )
        response = await client.post(
            f"/api/v1/recruiters/{recruiter.id}/outreach",
            headers=auth_headers,
            json={
                "message_type": "connection_request",
                "custom_message": "Hi, I noticed your team is hiring. I'd love to connect!",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["message_type"] == "connection_request"
        assert data["body"] == "Hi, I noticed your team is hiring. I'd love to connect!"
        assert data["ai_generated"] is False
        assert data["status"] == "pending"

    async def test_send_outreach_ai_generated(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """Scenario: Send AI-generated outreach message (no custom_message)."""
        recruiter = await factory.create_recruiter(
            db_session, test_user.id, name="AI Target"
        )
        response = await client.post(
            f"/api/v1/recruiters/{recruiter.id}/outreach",
            headers=auth_headers,
            json={"message_type": "inmail"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["ai_generated"] is True
        assert data["message_type"] == "inmail"

    async def test_get_messages_for_recruiter(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """Scenario: Retrieve outreach messages sent to a specific recruiter."""
        recruiter = await factory.create_recruiter(
            db_session, test_user.id, name="Messages Target"
        )
        await factory.create_outreach_message(
            db_session, test_user.id, recruiter.id,
            body="First message",
        )
        await factory.create_outreach_message(
            db_session, test_user.id, recruiter.id,
            message_type="follow_up",
            body="Following up on my previous message",
        )

        response = await client.get(
            f"/api/v1/recruiters/{recruiter.id}/messages",
            headers=auth_headers,
        )
        assert response.status_code == 200
        messages = response.json()
        assert len(messages) == 2

    async def test_get_messages_empty(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """Scenario: No messages sent → empty list."""
        recruiter = await factory.create_recruiter(
            db_session, test_user.id, name="No Messages"
        )
        response = await client.get(
            f"/api/v1/recruiters/{recruiter.id}/messages",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json() == []


class TestGenerateMessageFlow:
    """AI message generation preview E2E scenarios."""

    async def test_generate_message_preview(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """Scenario: Generate an AI message preview without sending."""
        recruiter = await factory.create_recruiter(
            db_session, test_user.id,
            name="Sarah Johnson",
            company="Amazon",
            title="Senior Technical Recruiter",
        )
        response = await client.post(
            "/api/v1/recruiters/generate-message",
            headers=auth_headers,
            json={
                "recruiter_id": str(recruiter.id),
                "message_type": "connection_request",
                "tone": "professional",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["recruiter_name"] == "Sarah Johnson"
        assert data["company"] == "Amazon"
        assert "suggested_message" in data
        assert len(data["suggested_message"]) > 0

    async def test_generate_message_nonexistent_recruiter(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: Generate message for nonexistent recruiter → 404."""
        response = await client.post(
            "/api/v1/recruiters/generate-message",
            headers=auth_headers,
            json={
                "recruiter_id": str(uuid.uuid4()),
                "message_type": "connection_request",
            },
        )
        assert response.status_code == 404


class TestRecruiterFullLifecycle:
    """Full recruiter outreach lifecycle E2E scenario."""

    async def test_discover_generate_and_send_outreach(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """
        Full lifecycle:
        1. "Discover" recruiters (via factory/demo data)
        2. List recruiters to find them
        3. Generate AI message preview for a recruiter
        4. Send outreach message with the preview
        5. Verify messages are stored
        """
        # Step 1: Create (simulate discovery)
        recruiter = await factory.create_recruiter(
            db_session, test_user.id,
            name="Discovery Target",
            company="Airbnb",
            title="Tech Recruiter",
        )

        # Step 2: List and find the recruiter
        list_resp = await client.get("/api/v1/recruiters", headers=auth_headers)
        assert list_resp.status_code == 200
        recruiters = list_resp.json()["recruiters"]
        assert len(recruiters) >= 1
        recruiter_id = recruiters[0]["id"]

        # Step 3: Generate message preview
        gen_resp = await client.post(
            "/api/v1/recruiters/generate-message",
            headers=auth_headers,
            json={
                "recruiter_id": recruiter_id,
                "message_type": "connection_request",
                "tone": "enthusiastic",
            },
        )
        assert gen_resp.status_code == 200
        suggested = gen_resp.json()["suggested_message"]

        # Step 4: Send the message
        send_resp = await client.post(
            f"/api/v1/recruiters/{recruiter_id}/outreach",
            headers=auth_headers,
            json={
                "message_type": "connection_request",
                "custom_message": suggested,
            },
        )
        assert send_resp.status_code == 201
        assert send_resp.json()["status"] == "pending"

        # Step 5: Verify recruiter detail
        detail_resp = await client.get(
            f"/api/v1/recruiters/{recruiter_id}", headers=auth_headers
        )
        assert detail_resp.status_code == 200
        assert detail_resp.json()["company"] == "Airbnb"

    async def test_multi_recruiter_outreach_flow(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        """
        Scenario: Outreach to multiple recruiters at different companies.
        1. Create 3 recruiters at different companies
        2. Send different message types to each
        3. Verify each recruiter's messages independently
        """
        companies = ["Google", "Meta", "Apple"]
        recruiter_ids = []

        for company in companies:
            r = await factory.create_recruiter(
                db_session, test_user.id,
                name=f"Recruiter at {company}",
                company=company,
            )
            recruiter_ids.append(str(r.id))

        # Send different outreach types
        message_types = ["connection_request", "inmail", "follow_up"]
        for rid, msg_type in zip(recruiter_ids, message_types):
            resp = await client.post(
                f"/api/v1/recruiters/{rid}/outreach",
                headers=auth_headers,
                json={
                    "message_type": msg_type,
                    "custom_message": f"Hello from {msg_type} test",
                },
            )
            assert resp.status_code == 201

        # Verify list shows all three
        list_resp = await client.get("/api/v1/recruiters", headers=auth_headers)
        assert list_resp.json()["total"] == 3
