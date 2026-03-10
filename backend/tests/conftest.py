"""
Test Configuration — Async SQLite in-memory database, test client, fixtures.

Uses httpx.AsyncClient + ASGI transport for true async E2E testing
against an in-memory SQLite database (no Docker dependencies needed).
"""

import asyncio
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import StaticPool, event
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.database import Base, get_db
from app.core.security import create_access_token, create_refresh_token, hash_password
from app.main import create_app
from app.models.application import Application, ApplicationMethod, ApplicationStatus
from app.models.job import JobListing, JobSource
from app.models.recruiter import ConnectionStatus, OutreachMessage, OutreachStatus, Recruiter
from app.models.resume import ResumeTemplate, ResumeVersion
from app.models.user import User

# ── Async SQLite Test Engine ──────────────────────────────────────

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DB_URL,
    echo=False,
    poolclass=StaticPool,
    connect_args={"check_same_thread": False},
)


# ── Fixtures ──────────────────────────────────────────────────────


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Create all tables before each test, drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a clean database session for each test."""
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client wired to in-memory DB."""
    app = create_app()

    async def override_get_db():
        # Always yield the same test session so data is shared across requests
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Demo Data Helpers ─────────────────────────────────────────────


class DemoDataFactory:
    """Factory for creating demo/mock data in the test database."""

    @staticmethod
    async def create_user(
        session: AsyncSession,
        *,
        email: str = "testuser@example.com",
        password: str = "TestPass123!",
        full_name: str = "Test User",
        phone: str | None = "+1234567890",
        headline: str | None = "Software Engineer",
        is_active: bool = True,
        is_verified: bool = False,
    ) -> User:
        """Create and persist a test user."""
        user = User(
            id=uuid.uuid4(),
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            phone=phone,
            headline=headline,
            is_active=is_active,
            is_verified=is_verified,
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
        return user

    @staticmethod
    async def create_job(
        session: AsyncSession,
        user_id: uuid.UUID,
        *,
        title: str = "Senior Backend Engineer",
        company: str = "TechCorp",
        location: str | None = "San Francisco, CA",
        description: str = "We are looking for a senior backend engineer...",
        source: JobSource = JobSource.LINKEDIN,
        source_url: str | None = None,
        match_score: float | None = 0.85,
        is_active: bool = True,
    ) -> JobListing:
        """Create and persist a test job listing."""
        job = JobListing(
            id=uuid.uuid4(),
            user_id=user_id,
            title=title,
            company=company,
            location=location,
            description=description,
            source=source,
            source_url=source_url or f"https://linkedin.com/jobs/{uuid.uuid4().hex[:8]}",
            match_score=match_score,
            match_reasoning="Good match based on skills",
            is_active=is_active,
            discovered_at=datetime.now(UTC),
        )
        session.add(job)
        await session.flush()
        await session.refresh(job)
        return job

    @staticmethod
    async def create_resume(
        session: AsyncSession,
        user_id: uuid.UUID,
        *,
        name: str = "Master Resume",
        latex_source: str = r"\documentclass{article}\begin{document}Hello World\end{document}",
        version_number: int = 1,
        is_master: bool = True,
        compilation_status: str = "pending",
    ) -> ResumeVersion:
        """Create and persist a test resume version."""
        resume = ResumeVersion(
            id=uuid.uuid4(),
            user_id=user_id,
            name=name,
            latex_source=latex_source,
            version_number=version_number,
            is_master=is_master,
            compilation_status=compilation_status,
        )
        session.add(resume)
        await session.flush()
        await session.refresh(resume)
        return resume

    @staticmethod
    async def create_resume_template(
        session: AsyncSession,
        *,
        name: str = "Professional Template",
        category: str = "general",
        latex_source: str = r"\documentclass{article}\begin{document}{{content}}\end{document}",
        is_active: bool = True,
    ) -> ResumeTemplate:
        """Create and persist a test resume template."""
        template = ResumeTemplate(
            id=uuid.uuid4(),
            name=name,
            description=f"A {name.lower()} for resumes",
            category=category,
            latex_source=latex_source,
            is_active=is_active,
        )
        session.add(template)
        await session.flush()
        await session.refresh(template)
        return template

    @staticmethod
    async def create_application(
        session: AsyncSession,
        user_id: uuid.UUID,
        job_id: uuid.UUID,
        resume_id: uuid.UUID,
        *,
        company: str = "TechCorp",
        role: str = "Senior Backend Engineer",
        status: ApplicationStatus = ApplicationStatus.DRAFT,
        method: ApplicationMethod = ApplicationMethod.MANUAL,
    ) -> Application:
        """Create and persist a test application."""
        application = Application(
            id=uuid.uuid4(),
            user_id=user_id,
            job_listing_id=job_id,
            resume_version_id=resume_id,
            company=company,
            role=role,
            status=status,
            method=method,
        )
        session.add(application)
        await session.flush()
        await session.refresh(application)
        return application

    @staticmethod
    async def create_recruiter(
        session: AsyncSession,
        user_id: uuid.UUID,
        *,
        name: str = "Jane Recruiter",
        title: str | None = "Technical Recruiter",
        company: str | None = "TechCorp",
        email: str | None = "jane@techcorp.com",
        linkedin_url: str | None = None,
        connection_status: ConnectionStatus = ConnectionStatus.NOT_CONNECTED,
        job_listing_id: uuid.UUID | None = None,
    ) -> Recruiter:
        """Create and persist a test recruiter."""
        recruiter = Recruiter(
            id=uuid.uuid4(),
            user_id=user_id,
            job_listing_id=job_listing_id,
            name=name,
            title=title,
            company=company,
            email=email,
            linkedin_url=linkedin_url or f"https://linkedin.com/in/{uuid.uuid4().hex[:8]}",
            connection_status=connection_status,
            platform="linkedin",
        )
        session.add(recruiter)
        await session.flush()
        await session.refresh(recruiter)
        return recruiter

    @staticmethod
    async def create_outreach_message(
        session: AsyncSession,
        user_id: uuid.UUID,
        recruiter_id: uuid.UUID,
        *,
        message_type: str = "connection_request",
        body: str = "Hi, I'd love to connect!",
        status: OutreachStatus = OutreachStatus.PENDING,
    ) -> OutreachMessage:
        """Create and persist a test outreach message."""
        msg = OutreachMessage(
            id=uuid.uuid4(),
            user_id=user_id,
            recruiter_id=recruiter_id,
            message_type=message_type,
            body=body,
            status=status,
        )
        session.add(msg)
        await session.flush()
        await session.refresh(msg)
        return msg


@pytest.fixture
def factory() -> type[DemoDataFactory]:
    """Provide the DemoDataFactory class for creating test data."""
    return DemoDataFactory


# ── Auth Helper Fixtures ──────────────────────────────────────────


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a default test user."""
    return await DemoDataFactory.create_user(db_session)


@pytest_asyncio.fixture
async def auth_headers(test_user: User) -> dict[str, str]:
    """Provide auth headers with a valid JWT for the test user."""
    token = create_access_token(str(test_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def auth_tokens(test_user: User) -> dict[str, str]:
    """Provide both access and refresh tokens for the test user."""
    access = create_access_token(str(test_user.id))
    refresh = create_refresh_token(str(test_user.id))
    return {
        "access_token": access,
        "refresh_token": refresh,
        "user_id": str(test_user.id),
    }
