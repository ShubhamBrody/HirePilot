"""
Auth Schemas — Registration, Login, Token responses, Credentials, Preferences.
"""

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    phone: str | None = None
    headline: str | None = None


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserProfileResponse(BaseModel):
    id: str
    email: str
    full_name: str
    phone: str | None = None
    headline: str | None = None
    summary: str | None = None
    skills: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
    job_search_keywords: str | None = None
    preferred_location: str | None = None
    is_active: bool
    is_verified: bool

    model_config = {"from_attributes": True}

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id_to_str(cls, v: object) -> str:
        return str(v)


class UserProfileUpdateRequest(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    headline: str | None = None
    summary: str | None = None
    skills: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None


# ── Credentials ──────────────────────────────────────────────────


class PlatformCredentialRequest(BaseModel):
    """Request to save encrypted platform credentials."""
    platform: str = Field(pattern="^(linkedin|indeed|naukri)$")
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=255)


class PlatformCredentialResponse(BaseModel):
    """Response showing which platforms have credentials stored."""
    platform: str
    configured: bool
    username: str | None = None  # Only the username, never the password


# ── Preferences ──────────────────────────────────────────────────


class JobPreferencesRequest(BaseModel):
    """Request to update job search preferences."""
    job_search_keywords: str | None = None
    preferred_location: str | None = None


class JobPreferencesResponse(BaseModel):
    """Response with current job search preferences."""
    job_search_keywords: str | None = None
    preferred_location: str | None = None

    model_config = {"from_attributes": True}


# ── Password Change ──────────────────────────────────────────────


class PasswordChangeRequest(BaseModel):
    """Request to change password."""
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)
