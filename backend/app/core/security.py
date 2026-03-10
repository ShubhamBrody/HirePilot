"""
Security Module — JWT, Password Hashing, Credential Encryption

Provides:
- JWT token creation and verification
- bcrypt password hashing
- AES-256 Fernet encryption for stored credentials
- OAuth2 bearer scheme
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from app.core.config import get_settings

settings = get_settings()

# ── Password Hashing ──────────────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


# ── JWT Tokens ────────────────────────────────────────────────────

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/login")


class TokenPayload(BaseModel):
    sub: str
    exp: datetime
    type: str = "access"


def create_access_token(subject: str, extra: dict[str, Any] | None = None) -> str:
    """Create a JWT access token."""
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {"sub": subject, "exp": expire, "type": "access"}
    if extra:
        payload.update(extra)
    return jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(subject: str) -> str:
    """Create a JWT refresh token."""
    expire = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_token_expire_days)
    payload = {"sub": subject, "exp": expire, "type": "refresh"}
    return jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str) -> TokenPayload:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
        return TokenPayload(**payload)
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def get_current_user_id(token: str = Depends(oauth2_scheme)) -> str:
    """FastAPI dependency — extract user ID from bearer token."""
    payload = decode_token(token)
    if payload.type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )
    return payload.sub


# ── Credential Encryption ────────────────────────────────────────

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = settings.credential_encryption_key.get_secret_value()
        if not key:
            raise ValueError("CREDENTIAL_ENCRYPTION_KEY is not set")
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt_credential(plaintext: str) -> str:
    """Encrypt a credential string using Fernet (AES-256-CBC)."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_credential(ciphertext: str) -> str:
    """Decrypt a Fernet-encrypted credential string."""
    return _get_fernet().decrypt(ciphertext.encode()).decode()
