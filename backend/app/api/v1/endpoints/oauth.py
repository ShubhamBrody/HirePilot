"""
OAuth Endpoints — Google and GitHub OAuth2 login.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.schemas.auth import TokenResponse
from app.services.oauth_service import OAuthService

router = APIRouter()
settings = get_settings()


class OAuthCallbackRequest(BaseModel):
    code: str
    redirect_uri: str


class OAuthURLResponse(BaseModel):
    url: str


# ── Google ────────────────────────────────────────────────────────


@router.get("/google/url", response_model=OAuthURLResponse)
async def google_auth_url(
    redirect_uri: str = Query(
        default=None,
        description="Frontend callback URL. Defaults to {oauth_redirect_base_url}/login/callback/google",
    ),
):
    """Get the Google OAuth2 authorization URL."""
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth is not configured",
        )
    uri = redirect_uri or f"{settings.oauth_redirect_base_url}/login/callback/google"
    service = OAuthService.__new__(OAuthService)
    return OAuthURLResponse(url=service.get_google_auth_url(uri))


@router.post("/google/callback", response_model=TokenResponse)
async def google_callback(
    data: OAuthCallbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """Exchange Google authorization code for JWT tokens."""
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth is not configured",
        )
    try:
        service = OAuthService(db)
        return await service.google_callback(data.code, data.redirect_uri)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ── GitHub ────────────────────────────────────────────────────────


@router.get("/github/url", response_model=OAuthURLResponse)
async def github_auth_url(
    redirect_uri: str = Query(
        default=None,
        description="Frontend callback URL. Defaults to {oauth_redirect_base_url}/login/callback/github",
    ),
):
    """Get the GitHub OAuth2 authorization URL."""
    if not settings.github_client_id:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="GitHub OAuth is not configured",
        )
    uri = redirect_uri or f"{settings.oauth_redirect_base_url}/login/callback/github"
    service = OAuthService.__new__(OAuthService)
    return OAuthURLResponse(url=service.get_github_auth_url(uri))


@router.post("/github/callback", response_model=TokenResponse)
async def github_callback(
    data: OAuthCallbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """Exchange GitHub authorization code for JWT tokens."""
    if not settings.github_client_id:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="GitHub OAuth is not configured",
        )
    try:
        service = OAuthService(db)
        return await service.github_callback(data.code, data.redirect_uri)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
