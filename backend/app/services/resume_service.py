"""
Resume Service — Version management, compilation, storage.
"""

import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resume import ResumeVersion
from app.repositories.resume_repo import ResumeRepository, ResumeTemplateRepository
from app.schemas.resume import (
    ResumeCompileResponse,
    ResumeListResponse,
    ResumeVersionCreateRequest,
    ResumeVersionResponse,
    ResumeVersionUpdateRequest,
)


class ResumeService:
    """Manages resume versions, templates, and PDF compilation."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.resume_repo = ResumeRepository(session)
        self.template_repo = ResumeTemplateRepository(session)

    async def create_version(
        self, user_id: str, data: ResumeVersionCreateRequest
    ) -> ResumeVersionResponse:
        """Create a new resume version."""
        version_number = await self.resume_repo.get_next_version_number(
            uuid.UUID(user_id)
        )

        # If this is set as master, unset existing master
        if data.is_master:
            existing_master = await self.resume_repo.get_master_resume(uuid.UUID(user_id))
            if existing_master:
                await self.resume_repo.update(existing_master, {"is_master": False})

        resume = ResumeVersion(
            user_id=uuid.UUID(user_id),
            name=data.name,
            description=data.description,
            latex_source=data.latex_source,
            version_number=version_number,
            template_id=uuid.UUID(data.template_id) if data.template_id else None,
            target_company=data.target_company,
            target_role=data.target_role,
            focus_area=data.focus_area,
            technologies=json.dumps(data.technologies) if data.technologies else None,
            is_master=data.is_master,
            compilation_status="pending",
        )
        resume = await self.resume_repo.create(resume)
        return ResumeVersionResponse.model_validate(resume)

    async def get_version(self, resume_id: str) -> ResumeVersionResponse:
        """Get a specific resume version."""
        resume = await self.resume_repo.get_by_id(uuid.UUID(resume_id))
        if not resume:
            raise ValueError("Resume version not found")
        return ResumeVersionResponse.model_validate(resume)

    async def list_versions(
        self, user_id: str, skip: int = 0, limit: int = 50
    ) -> ResumeListResponse:
        """List all resume versions for a user."""
        resumes = await self.resume_repo.get_user_resumes(
            uuid.UUID(user_id), skip=skip, limit=limit
        )
        total = await self.resume_repo.count_user_resumes(uuid.UUID(user_id))
        return ResumeListResponse(
            resumes=[ResumeVersionResponse.model_validate(r) for r in resumes],
            total=total,
        )

    async def update_version(
        self, resume_id: str, data: ResumeVersionUpdateRequest
    ) -> ResumeVersionResponse:
        """Update a resume version."""
        resume = await self.resume_repo.get_by_id(uuid.UUID(resume_id))
        if not resume:
            raise ValueError("Resume version not found")

        update_data = data.model_dump(exclude_unset=True)
        if "technologies" in update_data and update_data["technologies"]:
            update_data["technologies"] = json.dumps(update_data["technologies"])

        resume = await self.resume_repo.update(resume, update_data)
        return ResumeVersionResponse.model_validate(resume)

    async def delete_version(self, resume_id: str) -> None:
        """Delete a resume version."""
        resume = await self.resume_repo.get_by_id(uuid.UUID(resume_id))
        if not resume:
            raise ValueError("Resume version not found")
        await self.resume_repo.delete(resume)

    async def get_master_resume(self, user_id: str) -> ResumeVersionResponse | None:
        """Get the user's master resume."""
        resume = await self.resume_repo.get_master_resume(uuid.UUID(user_id))
        if not resume:
            return None
        return ResumeVersionResponse.model_validate(resume)

    async def compile_resume(self, resume_id: str) -> ResumeCompileResponse:
        """
        Trigger LaTeX compilation for a resume version.
        In production, this dispatches a Celery task.
        Returns immediately with 'compiling' status.
        """
        resume = await self.resume_repo.get_by_id(uuid.UUID(resume_id))
        if not resume:
            raise ValueError("Resume version not found")

        # Update status to compiling
        await self.resume_repo.update(resume, {"compilation_status": "compiling"})

        # In production: dispatch Celery task
        # compile_latex_task.delay(str(resume.id))

        return ResumeCompileResponse(
            resume_version_id=str(resume.id),
            status="compiling",
            pdf_url=None,
            errors=None,
        )
