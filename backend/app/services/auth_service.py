"""
Auth Service — Registration, login, token management.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.auth import (
    TokenResponse,
    UserProfileResponse,
    UserProfileUpdateRequest,
    UserRegisterRequest,
)


class AuthService:
    """Handles user authentication and profile management."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)

    async def register(self, data: UserRegisterRequest) -> TokenResponse:
        """Register a new user account and return JWT tokens."""
        # Check if email already exists
        if await self.user_repo.email_exists(data.email):
            raise ValueError("Email already registered")

        # Create user
        user = User(
            email=data.email,
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
            phone=data.phone,
            headline=data.headline,
        )
        user = await self.user_repo.create(user)
        # Auto-login: return tokens
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

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
        )

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

        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
        )

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
