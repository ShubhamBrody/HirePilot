"""
Auth Endpoints — Registration, Login, Profile, Credentials, Preferences.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.schemas.auth import (
    JobPreferencesRequest,
    JobPreferencesResponse,
    PasswordChangeRequest,
    PlatformCredentialRequest,
    PlatformCredentialResponse,
    RefreshTokenRequest,
    TokenResponse,
    UserLoginRequest,
    UserProfileResponse,
    UserProfileUpdateRequest,
    UserRegisterRequest,
)
from app.services.auth_service import AuthService

router = APIRouter()


# ── Auth ─────────────────────────────────────────────────────────


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(data: UserRegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user account and return JWT tokens."""
    try:
        service = AuthService(db)
        return await service.register(data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate and receive JWT tokens."""
    try:
        service = AuthService(db)
        return await service.login(data.email, data.password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(data: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    """Refresh access token using refresh token."""
    try:
        service = AuthService(db)
        return await service.refresh_token(data.refresh_token)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


# ── Profile ──────────────────────────────────────────────────────


@router.get("/me", response_model=UserProfileResponse)
async def get_profile(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get the current user's profile."""
    try:
        service = AuthService(db)
        return await service.get_profile(user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/me", response_model=UserProfileResponse)
async def update_profile(
    data: UserProfileUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Update the current user's profile."""
    try:
        service = AuthService(db)
        return await service.update_profile(user_id, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete the current user's account."""
    try:
        service = AuthService(db)
        await service.delete_account(user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    data: PasswordChangeRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Change the current user's password."""
    try:
        service = AuthService(db)
        await service.change_password(user_id, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ── Platform Credentials ────────────────────────────────────────


@router.get("/credentials", response_model=list[PlatformCredentialResponse])
async def get_credentials(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get status of stored platform credentials."""
    service = AuthService(db)
    return await service.get_credentials_status(user_id)


@router.post("/credentials", response_model=PlatformCredentialResponse)
async def save_credential(
    data: PlatformCredentialRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Save encrypted platform credentials."""
    try:
        service = AuthService(db)
        return await service.save_credential(
            user_id, data.platform, data.username, data.password
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/credentials/{platform}", response_model=PlatformCredentialResponse)
async def delete_credential(
    platform: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Remove stored credentials for a platform."""
    try:
        service = AuthService(db)
        return await service.delete_credential(user_id, platform)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ── Job Preferences ─────────────────────────────────────────────


@router.get("/preferences", response_model=JobPreferencesResponse)
async def get_preferences(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get the user's job search preferences."""
    service = AuthService(db)
    return await service.get_preferences(user_id)


@router.put("/preferences", response_model=JobPreferencesResponse)
async def update_preferences(
    data: JobPreferencesRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Update job search preferences."""
    try:
        service = AuthService(db)
        return await service.update_preferences(
            user_id, data.model_dump(exclude_none=True)
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
