"""
Tests for Subscription endpoints — Plans, billing, feature gating.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


@pytest.mark.asyncio
async def test_list_plans(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/subscription/plans", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "plans" in data
    assert len(data["plans"]) == 3
    plan_names = [p["name"] for p in data["plans"]]
    assert "free" in plan_names
    assert "pro" in plan_names
    assert "enterprise" in plan_names
    assert data["current_plan"] == "free"


@pytest.mark.asyncio
async def test_get_current_subscription_defaults_to_free(
    client: AsyncClient, auth_headers: dict
):
    resp = await client.get("/api/v1/subscription/current", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["plan"] == "free"
    assert data["price_monthly"] == 0.0
    assert data["ai_tailoring_enabled"] is False


@pytest.mark.asyncio
async def test_change_plan_to_pro(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/v1/subscription/change-plan",
        json={"plan": "pro"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["plan"] == "pro"
    assert data["price_monthly"] == 9.99
    assert data["ai_tailoring_enabled"] is True
    assert data["autonomous_mode_enabled"] is False


@pytest.mark.asyncio
async def test_change_plan_to_enterprise(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/v1/subscription/change-plan",
        json={"plan": "enterprise"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["plan"] == "enterprise"
    assert data["price_monthly"] == 29.99
    assert data["autonomous_mode_enabled"] is True


@pytest.mark.asyncio
async def test_change_plan_invalid(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/v1/subscription/change-plan",
        json={"plan": "platinum"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_downgrade_to_free(client: AsyncClient, auth_headers: dict):
    # Upgrade first
    await client.post(
        "/api/v1/subscription/change-plan",
        json={"plan": "pro"},
        headers=auth_headers,
    )
    # Downgrade
    resp = await client.post(
        "/api/v1/subscription/change-plan",
        json={"plan": "free"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["plan"] == "free"
    assert resp.json()["price_monthly"] == 0.0


@pytest.mark.asyncio
async def test_mock_payment(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/v1/subscription/mock-payment",
        json={"card_last4": "4242"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["mock_card_last4"] == "4242"


@pytest.mark.asyncio
async def test_feature_gate_free_plan(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/subscription/check-feature/ai_tailoring", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["allowed"] is False
    assert data["current_plan"] == "free"
    assert data["required_plan"] == "pro"


@pytest.mark.asyncio
async def test_feature_gate_after_upgrade(client: AsyncClient, auth_headers: dict):
    await client.post(
        "/api/v1/subscription/change-plan",
        json={"plan": "pro"},
        headers=auth_headers,
    )
    resp = await client.get("/api/v1/subscription/check-feature/ai_tailoring", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["allowed"] is True


@pytest.mark.asyncio
async def test_feature_gate_unknown_feature(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/subscription/check-feature/nonexistent", headers=auth_headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_enterprise_auto_assign(
    client: AsyncClient, db_session: AsyncSession
):
    """The special email should auto-assign Enterprise plan."""
    from app.core.security import create_access_token, hash_password
    import uuid

    user = User(
        id=uuid.uuid4(),
        email="recruitshubhamtiwari@gmail.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Shubham Tiwari",
    )
    db_session.add(user)
    await db_session.flush()

    token = create_access_token(str(user.id))
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get("/api/v1/subscription/current", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["plan"] == "enterprise"
    assert resp.json()["autonomous_mode_enabled"] is True
