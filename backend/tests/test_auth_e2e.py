"""
E2E Scenario Tests — Auth Flow

Tests the complete authentication lifecycle:
1. User registration → receives tokens
2. User login → receives tokens
3. Token refresh → new access token
4. Get profile → user data
5. Update profile → modified fields
6. Duplicate email registration → 400 error
7. Wrong password login → 401 error
8. Inactive user login → 401 error
9. Invalid token access → 401 error
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

pytestmark = pytest.mark.asyncio


# ── Scenario 1: Full Registration + Login Lifecycle ──────────────


class TestRegistrationFlow:
    """Complete user registration E2E scenarios."""

    async def test_register_new_user_returns_tokens(self, client: AsyncClient):
        """Scenario: New user registers and receives JWT tokens."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "SecurePass123!",
                "full_name": "New User",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_register_with_optional_fields(self, client: AsyncClient):
        """Scenario: Registration with phone and headline."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "detailed@example.com",
                "password": "SecurePass123!",
                "full_name": "Detailed User",
                "phone": "+1-555-0199",
                "headline": "Full-Stack Developer",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data

        # Verify profile has the optional fields
        headers = {"Authorization": f"Bearer {data['access_token']}"}
        profile = await client.get("/api/v1/auth/me", headers=headers)
        assert profile.status_code == 200
        profile_data = profile.json()
        assert profile_data["phone"] == "+1-555-0199"
        assert profile_data["headline"] == "Full-Stack Developer"

    async def test_register_duplicate_email_returns_400(
        self, client: AsyncClient, test_user: User
    ):
        """Scenario: Cannot register with an already-used email."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": test_user.email,  # "testuser@example.com"
                "password": "AnotherPass123!",
                "full_name": "Duplicate User",
            },
        )
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()

    async def test_register_short_password_returns_422(self, client: AsyncClient):
        """Scenario: Password too short triggers validation error."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "short@example.com",
                "password": "abc",
                "full_name": "Short Pass User",
            },
        )
        assert response.status_code == 422  # Pydantic validation

    async def test_register_invalid_email_returns_422(self, client: AsyncClient):
        """Scenario: Invalid email format triggers validation error."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "password": "SecurePass123!",
                "full_name": "Bad Email User",
            },
        )
        assert response.status_code == 422

    async def test_register_missing_fields_returns_422(self, client: AsyncClient):
        """Scenario: Missing required fields triggers validation error."""
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "partial@example.com"},
        )
        assert response.status_code == 422


# ── Scenario 2: Login Flow ──────────────────────────────────────


class TestLoginFlow:
    """Complete user login E2E scenarios."""

    async def test_login_valid_credentials(self, client: AsyncClient, test_user: User):
        """Scenario: Correct email/password returns JWT tokens."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "testuser@example.com",
                "password": "TestPass123!",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password_returns_401(
        self, client: AsyncClient, test_user: User
    ):
        """Scenario: Wrong password returns authentication error."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "testuser@example.com",
                "password": "WrongPassword!",
            },
        )
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    async def test_login_nonexistent_email_returns_401(self, client: AsyncClient):
        """Scenario: Unregistered email returns auth error."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "nobody@example.com",
                "password": "SomePass123!",
            },
        )
        assert response.status_code == 401

    async def test_login_inactive_user_returns_401(
        self, client: AsyncClient, db_session: AsyncSession, factory
    ):
        """Scenario: Deactivated user cannot login."""
        await factory.create_user(
            db_session,
            email="inactive@example.com",
            password="InactivePass!1",
            full_name="Inactive User",
            is_active=False,
        )
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "inactive@example.com",
                "password": "InactivePass!1",
            },
        )
        assert response.status_code == 401


# ── Scenario 3: Token Refresh Flow ──────────────────────────────


class TestTokenRefreshFlow:
    """Token refresh E2E scenarios."""

    async def test_refresh_with_valid_token(
        self, client: AsyncClient, auth_tokens: dict[str, str]
    ):
        """Scenario: Valid refresh token issues new access + refresh tokens."""
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": auth_tokens["refresh_token"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_refresh_with_access_token_fails(
        self, client: AsyncClient, auth_tokens: dict[str, str]
    ):
        """Scenario: Using access_token as refresh_token fails."""
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": auth_tokens["access_token"]},
        )
        assert response.status_code == 401

    async def test_refresh_with_invalid_token_fails(self, client: AsyncClient):
        """Scenario: Garbage token fails refresh."""
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid.garbage.token"},
        )
        assert response.status_code == 401


# ── Scenario 4: Profile Management Flow ─────────────────────────


class TestProfileFlow:
    """Profile retrieval and update E2E scenarios."""

    async def test_get_profile_authenticated(
        self, client: AsyncClient, auth_headers: dict[str, str], test_user: User
    ):
        """Scenario: Authenticated user retrieves own profile."""
        response = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "testuser@example.com"
        assert data["full_name"] == "Test User"
        assert data["is_active"] is True

    async def test_get_profile_unauthenticated_returns_401(self, client: AsyncClient):
        """Scenario: Unauthenticated request to /me returns 401."""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    async def test_update_profile_partial_fields(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Scenario: PATCH /me updates only provided fields."""
        response = await client.patch(
            "/api/v1/auth/me",
            headers=auth_headers,
            json={
                "headline": "Senior Python Developer",
                "location": "New York, NY",
                "linkedin_url": "https://linkedin.com/in/testuser",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["headline"] == "Senior Python Developer"
        assert data["location"] == "New York, NY"
        assert data["linkedin_url"] == "https://linkedin.com/in/testuser"
        # Unchanged fields preserved
        assert data["full_name"] == "Test User"

    async def test_update_profile_unauthenticated_returns_401(self, client: AsyncClient):
        """Scenario: Unauthenticated PATCH /me returns 401."""
        response = await client.patch(
            "/api/v1/auth/me",
            json={"headline": "Hacker"},
        )
        assert response.status_code == 401


# ── Scenario 5: Full Registration → Login → Profile Lifecycle ───


class TestFullAuthLifecycle:
    """End-to-end auth lifecycle spanning register, login, and profile."""

    async def test_register_then_login_then_profile(self, client: AsyncClient):
        """
        Full lifecycle:
        1. Register new account
        2. Use returned tokens to get profile
        3. Login with same credentials
        4. Use login tokens to update profile
        5. Verify profile was updated
        """
        # Step 1: Register
        reg_resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "lifecycle@example.com",
                "password": "LifeCycle123!",
                "full_name": "Lifecycle User",
            },
        )
        assert reg_resp.status_code == 201
        reg_tokens = reg_resp.json()
        reg_headers = {"Authorization": f"Bearer {reg_tokens['access_token']}"}

        # Step 2: Get profile with registration tokens
        profile_resp = await client.get("/api/v1/auth/me", headers=reg_headers)
        assert profile_resp.status_code == 200
        assert profile_resp.json()["email"] == "lifecycle@example.com"

        # Step 3: Login with same credentials
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "lifecycle@example.com", "password": "LifeCycle123!"},
        )
        assert login_resp.status_code == 200
        login_tokens = login_resp.json()
        login_headers = {"Authorization": f"Bearer {login_tokens['access_token']}"}

        # Step 4: Update profile with login tokens
        update_resp = await client.patch(
            "/api/v1/auth/me",
            headers=login_headers,
            json={
                "headline": "Updated Headline",
                "skills": "Python,FastAPI,React",
                "github_url": "https://github.com/lifecycleuser",
            },
        )
        assert update_resp.status_code == 200

        # Step 5: Verify update persisted
        verify_resp = await client.get("/api/v1/auth/me", headers=login_headers)
        assert verify_resp.status_code == 200
        verify_data = verify_resp.json()
        assert verify_data["headline"] == "Updated Headline"
        assert verify_data["skills"] == "Python,FastAPI,React"
        assert verify_data["github_url"] == "https://github.com/lifecycleuser"

    async def test_register_then_refresh_token(self, client: AsyncClient):
        """
        Lifecycle: Register → Refresh token → Use new token for profile.
        """
        # Register
        reg_resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "refreshtest@example.com",
                "password": "RefreshMe123!",
                "full_name": "Refresh Test",
            },
        )
        assert reg_resp.status_code == 201
        initial_tokens = reg_resp.json()

        # Refresh
        refresh_resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": initial_tokens["refresh_token"]},
        )
        assert refresh_resp.status_code == 200
        new_tokens = refresh_resp.json()

        # Use new token to access profile
        headers = {"Authorization": f"Bearer {new_tokens['access_token']}"}
        profile = await client.get("/api/v1/auth/me", headers=headers)
        assert profile.status_code == 200
        assert profile.json()["email"] == "refreshtest@example.com"
