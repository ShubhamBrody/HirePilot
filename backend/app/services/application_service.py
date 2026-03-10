"""
Application Service — Application tracking, status management, analytics.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application, ApplicationStatus
from app.repositories.application_repo import ApplicationRepository
from app.repositories.job_repo import JobRepository
from app.schemas.application import (
    ApplicationAnalytics,
    ApplicationCreateRequest,
    ApplicationFilters,
    ApplicationListResponse,
    ApplicationResponse,
    ApplicationStatusUpdateRequest,
)


class ApplicationService:
    """Manages job application lifecycle and tracking."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.app_repo = ApplicationRepository(session)
        self.job_repo = JobRepository(session)

    async def create_application(
        self, user_id: str, data: ApplicationCreateRequest
    ) -> ApplicationResponse:
        """Create a new job application."""
        uid = uuid.UUID(user_id)
        job_id = uuid.UUID(data.job_listing_id)

        # Check for duplicate application
        if await self.app_repo.application_exists(uid, job_id):
            raise ValueError("You have already applied to this job")

        # Get job details for snapshot
        job = await self.job_repo.get_by_id(job_id)
        if not job:
            raise ValueError("Job listing not found")

        application = Application(
            user_id=uid,
            job_listing_id=job_id,
            resume_version_id=uuid.UUID(data.resume_version_id),
            company=job.company,
            role=job.title,
            job_description_snapshot=job.description,
            cover_letter=data.cover_letter,
            notes=data.notes,
            status=ApplicationStatus.DRAFT,
            method=data.method,
        )
        application = await self.app_repo.create(application)
        return ApplicationResponse.model_validate(application)

    async def list_applications(
        self, user_id: str, filters: ApplicationFilters
    ) -> ApplicationListResponse:
        """List applications with filtering and pagination."""
        uid = uuid.UUID(user_id)
        applications = await self.app_repo.get_user_applications(
            uid,
            skip=(filters.page - 1) * filters.page_size,
            limit=filters.page_size,
            status=filters.status,
            company=filters.company,
            role=filters.role,
            date_from=filters.date_from,
            date_to=filters.date_to,
        )
        total = await self.app_repo.count_user_applications(uid, filters.status)
        return ApplicationListResponse(
            applications=[ApplicationResponse.model_validate(a) for a in applications],
            total=total,
            page=filters.page,
            page_size=filters.page_size,
        )

    async def update_status(
        self, application_id: str, data: ApplicationStatusUpdateRequest
    ) -> ApplicationResponse:
        """Update an application's status."""
        app = await self.app_repo.get_by_id(uuid.UUID(application_id))
        if not app:
            raise ValueError("Application not found")

        update_data: dict[str, object] = {"status": data.status}
        if data.notes:
            update_data["notes"] = data.notes

        # Set date fields based on status transitions
        if data.status == ApplicationStatus.APPLIED:
            update_data["applied_date"] = datetime.now(UTC)
        elif data.status in (
            ApplicationStatus.INTERVIEW,
            ApplicationStatus.OFFER,
            ApplicationStatus.REJECTED,
        ):
            update_data["response_date"] = datetime.now(UTC)

        app = await self.app_repo.update(app, update_data)
        return ApplicationResponse.model_validate(app)

    async def get_analytics(self, user_id: str) -> ApplicationAnalytics:
        """Get application analytics for a user."""
        uid = uuid.UUID(user_id)
        total = await self.app_repo.count_user_applications(uid)
        status_counts = await self.app_repo.get_status_counts(uid)

        interview_count = status_counts.get("interview", 0) + status_counts.get("offer", 0)
        response_count = interview_count + status_counts.get("rejected", 0)

        return ApplicationAnalytics(
            total_applications=total,
            by_status=status_counts,
            by_company={},       # TODO: implement company grouping query
            by_method={},        # TODO: implement method grouping query
            weekly_trend=[],     # TODO: implement weekly trend query
            response_rate=response_count / total if total > 0 else 0.0,
            interview_rate=interview_count / total if total > 0 else 0.0,
        )
