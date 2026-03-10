"""
OAuth Service — Google and GitHub OAuth2 login/signup.

Handles the OAuth callback flow:
1. Frontend redirects user to provider's authorization URL
2. Provider redirects back to frontend with an authorization code
3. Frontend sends the code to our backend
4. Backend exchanges code for tokens, fetches user info, creates/links account
"""

import secrets

import httpx

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token, create_refresh_token, hash_password
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.auth import TokenResponse

settings = get_settings()


class OAuthService:
    """Handles OAuth2 authentication with Google and GitHub."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)

    # ── Google ────────────────────────────────────────────────

    def get_google_auth_url(self, redirect_uri: str) -> str:
        """Build the Google OAuth2 authorization URL."""
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "prompt": "consent",
        }
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        return f"https://accounts.google.com/o/oauth2/v2/auth?{qs}"

    async def google_callback(self, code: str, redirect_uri: str) -> TokenResponse:
        """Exchange Google auth code for user tokens."""
        async with httpx.AsyncClient() as client:
            # Exchange code for Google tokens
            token_resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret.get_secret_value(),
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            if token_resp.status_code != 200:
                raise ValueError(f"Google token exchange failed: {token_resp.text}")
            tokens = token_resp.json()

            # Fetch user info from Google
            userinfo_resp = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            if userinfo_resp.status_code != 200:
                raise ValueError("Failed to fetch Google user info")
            info = userinfo_resp.json()

        return await self._get_or_create_oauth_user(
            provider="google",
            provider_id=info["id"],
            email=info["email"],
            full_name=info.get("name", info["email"].split("@")[0]),
            avatar_url=info.get("picture"),
        )

    # ── GitHub ────────────────────────────────────────────────

    def get_github_auth_url(self, redirect_uri: str) -> str:
        """Build the GitHub OAuth2 authorization URL."""
        params = {
            "client_id": settings.github_client_id,
            "redirect_uri": redirect_uri,
            "scope": "read:user user:email",
        }
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        return f"https://github.com/login/oauth/authorize?{qs}"

    async def github_callback(self, code: str, redirect_uri: str) -> TokenResponse:
        """Exchange GitHub auth code for user tokens."""
        async with httpx.AsyncClient() as client:
            # Exchange code for GitHub access token
            token_resp = await client.post(
                "https://github.com/login/oauth/access_token",
                json={
                    "client_id": settings.github_client_id,
                    "client_secret": settings.github_client_secret.get_secret_value(),
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                headers={"Accept": "application/json"},
            )
            if token_resp.status_code != 200:
                raise ValueError(f"GitHub token exchange failed: {token_resp.text}")
            tokens = token_resp.json()
            if "error" in tokens:
                raise ValueError(f"GitHub OAuth error: {tokens['error_description']}")

            access_token = tokens["access_token"]

            # Fetch user info
            user_resp = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            if user_resp.status_code != 200:
                raise ValueError("Failed to fetch GitHub user info")
            info = user_resp.json()

            # Fetch primary email if not public
            email = info.get("email")
            if not email:
                emails_resp = await client.get(
                    "https://api.github.com/user/emails",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/vnd.github+json",
                    },
                )
                if emails_resp.status_code == 200:
                    for e in emails_resp.json():
                        if e.get("primary") and e.get("verified"):
                            email = e["email"]
                            break
            if not email:
                raise ValueError("No verified email found on GitHub account")

        return await self._get_or_create_oauth_user(
            provider="github",
            provider_id=str(info["id"]),
            email=email,
            full_name=info.get("name") or info.get("login", email.split("@")[0]),
            avatar_url=info.get("avatar_url"),
        )

    # ── Shared ────────────────────────────────────────────────

    async def _get_or_create_oauth_user(
        self,
        *,
        provider: str,
        provider_id: str,
        email: str,
        full_name: str,
        avatar_url: str | None,
    ) -> TokenResponse:
        """Find existing user by email or create a new OAuth user."""
        user = await self.user_repo.get_by_email(email)
        if user:
            # Link OAuth if not already linked
            if not user.oauth_provider:
                update_data: dict = {
                    "oauth_provider": provider,
                    "oauth_provider_id": provider_id,
                }
                if avatar_url:
                    update_data["avatar_url"] = avatar_url
                await self.user_repo.update(user, update_data)
        else:
            # Create new user with random password (OAuth-only)
            user = User(
                email=email,
                hashed_password=hash_password(secrets.token_urlsafe(32)),
                full_name=full_name,
                oauth_provider=provider,
                oauth_provider_id=provider_id,
                avatar_url=avatar_url,
                is_verified=True,
            )
            user = await self.user_repo.create(user)

        access_token = create_access_token(str(user.id))
        refresh_token = create_refresh_token(str(user.id))
        return TokenResponse(access_token=access_token, refresh_token=refresh_token)
