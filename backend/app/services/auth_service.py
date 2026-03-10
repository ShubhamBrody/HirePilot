"""
Auth Service — Registration, login, token management, credentials, preferences.
"""

import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    encrypt_credential,
    decrypt_credential,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.auth import (
    JobPreferencesResponse,
    PasswordChangeRequest,
    PlatformCredentialResponse,
    TokenResponse,
    UserProfileResponse,
    UserProfileUpdateRequest,
    UserRegisterRequest,
)

# Map platform name → model field
_CRED_FIELD_MAP = {
    "linkedin": "encrypted_linkedin_creds",
    "indeed": "encrypted_indeed_creds",
    "naukri": "encrypted_naukri_creds",
}


class AuthService:
    """Handles user authentication and profile management."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)

    # ── Auth ─────────────────────────────────────────────────────

    async def register(self, data: UserRegisterRequest) -> TokenResponse:
        """Register a new user account and return JWT tokens."""
        if await self.user_repo.email_exists(data.email):
            raise ValueError("Email already registered")

        user = User(
            email=data.email,
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
            phone=data.phone,
            headline=data.headline,
        )
        user = await self.user_repo.create(user)
        access_token = create_access_token(str(user.id))
        refresh_token = create_refresh_token(str(user.id))
        return TokenResponse(access_token=access_token, refresh_token=refresh_token)

    async def login(self, email: str, password: str) -> TokenResponse:
        """Authenticate user and return JWT tokens."""
        user = await self.user_repo.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise ValueError("Invalid email or password")
        if not user.is_active:
            raise ValueError("Account is deactivated")

        access_token = create_access_token(str(user.id))
        refresh_token = create_refresh_token(str(user.id))
        return TokenResponse(access_token=access_token, refresh_token=refresh_token)

    async def refresh_token(self, refresh_token_str: str) -> TokenResponse:
        """Issue new tokens using a valid refresh token."""
        payload = decode_token(refresh_token_str)
        if payload.type != "refresh":
            raise ValueError("Invalid token type")

        user = await self.user_repo.get_by_id(uuid.UUID(payload.sub))
        if not user or not user.is_active:
            raise ValueError("User not found or deactivated")

        access_token = create_access_token(str(user.id))
        new_refresh_token = create_refresh_token(str(user.id))
        return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)

    # ── Profile ──────────────────────────────────────────────────

    async def get_profile(self, user_id: str) -> UserProfileResponse:
        """Get user profile by ID."""
        user = await self.user_repo.get_by_id(uuid.UUID(user_id))
        if not user:
            raise ValueError("User not found")
        return UserProfileResponse.model_validate(user)

    async def update_profile(
        self, user_id: str, data: UserProfileUpdateRequest
    ) -> UserProfileResponse:
        """Update user profile."""
        user = await self.user_repo.get_by_id(uuid.UUID(user_id))
        if not user:
            raise ValueError("User not found")

        update_data = data.model_dump(exclude_unset=True)
        user = await self.user_repo.update(user, update_data)
        return UserProfileResponse.model_validate(user)

    async def change_password(self, user_id: str, data: PasswordChangeRequest) -> None:
        """Change user password after verifying the current one."""
        user = await self.user_repo.get_by_id(uuid.UUID(user_id))
        if not user:
            raise ValueError("User not found")
        if not verify_password(data.current_password, user.hashed_password):
            raise ValueError("Current password is incorrect")

        user = await self.user_repo.update(
            user, {"hashed_password": hash_password(data.new_password)}
        )

    async def delete_account(self, user_id: str) -> None:
        """Permanently delete a user account."""
        user = await self.user_repo.get_by_id(uuid.UUID(user_id))
        if not user:
            raise ValueError("User not found")
        await self.user_repo.delete(user)

    # ── Platform Credentials ─────────────────────────────────────

    async def get_credentials_status(
        self, user_id: str
    ) -> list[PlatformCredentialResponse]:
        """Return which platforms have stored credentials."""
        user = await self.user_repo.get_by_id(uuid.UUID(user_id))
        if not user:
            raise ValueError("User not found")

        results: list[PlatformCredentialResponse] = []
        for platform, field in _CRED_FIELD_MAP.items():
            encrypted = getattr(user, field)
            username = None
            if encrypted:
                try:
                    creds = json.loads(decrypt_credential(encrypted))
                    username = creds.get("username")
                except Exception:
                    pass
            results.append(
                PlatformCredentialResponse(
                    platform=platform,
                    configured=bool(encrypted),
                    username=username,
                )
            )
        return results

    async def save_credential(
        self, user_id: str, platform: str, username: str, password: str
    ) -> PlatformCredentialResponse:
        """Encrypt and save platform credentials."""
        user = await self.user_repo.get_by_id(uuid.UUID(user_id))
        if not user:
            raise ValueError("User not found")

        field = _CRED_FIELD_MAP.get(platform)
        if not field:
            raise ValueError(f"Unsupported platform: {platform}")

        cred_json = json.dumps({"username": username, "password": password})
        encrypted = encrypt_credential(cred_json)
        await self.user_repo.update(user, {field: encrypted})
        return PlatformCredentialResponse(
            platform=platform, configured=True, username=username
        )

    async def delete_credential(
        self, user_id: str, platform: str
    ) -> PlatformCredentialResponse:
        """Remove stored credentials for a platform."""
        user = await self.user_repo.get_by_id(uuid.UUID(user_id))
        if not user:
            raise ValueError("User not found")

        field = _CRED_FIELD_MAP.get(platform)
        if not field:
            raise ValueError(f"Unsupported platform: {platform}")

        await self.user_repo.update(user, {field: None})
        return PlatformCredentialResponse(
            platform=platform, configured=False, username=None
        )

    # ── Job Preferences ──────────────────────────────────────────

    async def get_preferences(self, user_id: str) -> JobPreferencesResponse:
        """Get the user's job search preferences."""
        user = await self.user_repo.get_by_id(uuid.UUID(user_id))
        if not user:
            raise ValueError("User not found")
        return JobPreferencesResponse.model_validate(user)

    async def update_preferences(
        self, user_id: str, keywords: str | None, location: str | None
    ) -> JobPreferencesResponse:
        """Update job search preferences."""
        user = await self.user_repo.get_by_id(uuid.UUID(user_id))
        if not user:
            raise ValueError("User not found")

        update: dict[str, str | None] = {}
        if keywords is not None:
            update["job_search_keywords"] = keywords
        if location is not None:
            update["preferred_location"] = location
        if update:
            user = await self.user_repo.update(user, update)
        return JobPreferencesResponse.model_validate(user)
