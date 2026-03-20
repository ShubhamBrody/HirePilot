"""
Profile Endpoints — Work Experience & Education CRUD, AI Career Summary.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.education import Education
from app.models.work_experience import WorkExperience
from app.repositories.education_repo import EducationRepository
from app.repositories.work_experience_repo import WorkExperienceRepository
from app.schemas.education import (
    EducationChoicesResponse,
    EducationCreate,
    EducationListResponse,
    EducationResponse,
    EducationUpdate,
)
from app.schemas.work_experience import (
    WorkExperienceCreate,
    WorkExperienceListResponse,
    WorkExperienceResponse,
    WorkExperienceUpdate,
)

router = APIRouter()


# ── Work Experience ──────────────────────────────────────────────


@router.get("/work-experience", response_model=WorkExperienceListResponse)
async def list_work_experiences(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    repo = WorkExperienceRepository(db)
    entries = await repo.get_by_user(uuid.UUID(user_id))
    return WorkExperienceListResponse(
        experiences=[WorkExperienceResponse.model_validate(e) for e in entries],
        total=len(entries),
    )


@router.post("/work-experience", response_model=WorkExperienceResponse, status_code=status.HTTP_201_CREATED)
async def create_work_experience(
    data: WorkExperienceCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    repo = WorkExperienceRepository(db)
    entry = WorkExperience(
        user_id=uuid.UUID(user_id),
        company=data.company,
        role=data.role,
        location=data.location,
        description=data.description,
        start_date=date.fromisoformat(data.start_date) if data.start_date else None,
        end_date=date.fromisoformat(data.end_date) if data.end_date and not data.is_current else None,
        is_current=data.is_current,
        sort_order=data.sort_order,
    )
    created = await repo.create(entry)
    await db.commit()
    return WorkExperienceResponse.model_validate(created)


@router.put("/work-experience/{exp_id}", response_model=WorkExperienceResponse)
async def update_work_experience(
    exp_id: str,
    data: WorkExperienceUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    repo = WorkExperienceRepository(db)
    entry = await repo.get_by_id(uuid.UUID(exp_id))
    if not entry or str(entry.user_id) != user_id:
        raise HTTPException(status_code=404, detail="Work experience not found")

    updates = data.model_dump(exclude_unset=True)
    if "start_date" in updates and updates["start_date"]:
        updates["start_date"] = date.fromisoformat(updates["start_date"])
    if "end_date" in updates and updates["end_date"]:
        updates["end_date"] = date.fromisoformat(updates["end_date"])
    if updates.get("is_current"):
        updates["end_date"] = None

    updated = await repo.update(entry, updates)
    await db.commit()
    return WorkExperienceResponse.model_validate(updated)


@router.delete("/work-experience/{exp_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_work_experience(
    exp_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    repo = WorkExperienceRepository(db)
    entry = await repo.get_by_id(uuid.UUID(exp_id))
    if not entry or str(entry.user_id) != user_id:
        raise HTTPException(status_code=404, detail="Work experience not found")
    await repo.delete(entry)
    await db.commit()


@router.put("/work-experience", response_model=WorkExperienceListResponse)
async def bulk_save_work_experiences(
    data: list[WorkExperienceCreate],
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Replace all work experiences for the user (used by onboarding)."""
    repo = WorkExperienceRepository(db)
    await repo.delete_all_for_user(uuid.UUID(user_id))
    entries = []
    for i, item in enumerate(data):
        entry = WorkExperience(
            user_id=uuid.UUID(user_id),
            company=item.company,
            role=item.role,
            location=item.location,
            description=item.description,
            start_date=date.fromisoformat(item.start_date) if item.start_date else None,
            end_date=date.fromisoformat(item.end_date) if item.end_date and not item.is_current else None,
            is_current=item.is_current,
            sort_order=i,
        )
        created = await repo.create(entry)
        entries.append(created)
    await db.commit()
    return WorkExperienceListResponse(
        experiences=[WorkExperienceResponse.model_validate(e) for e in entries],
        total=len(entries),
    )


# ── Education ────────────────────────────────────────────────────


@router.get("/education/choices", response_model=EducationChoicesResponse)
async def get_education_choices():
    """Return available degree and field of study choices."""
    return EducationChoicesResponse()


@router.get("/education", response_model=EducationListResponse)
async def list_educations(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    repo = EducationRepository(db)
    entries = await repo.get_by_user(uuid.UUID(user_id))
    return EducationListResponse(
        educations=[EducationResponse.model_validate(e) for e in entries],
        total=len(entries),
    )


@router.post("/education", response_model=EducationResponse, status_code=status.HTTP_201_CREATED)
async def create_education(
    data: EducationCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    repo = EducationRepository(db)
    entry = Education(
        user_id=uuid.UUID(user_id),
        degree=data.degree,
        custom_degree=data.custom_degree if data.degree == "Other" else None,
        field_of_study=data.field_of_study,
        custom_field=data.custom_field if data.field_of_study == "Other" else None,
        institution=data.institution,
        start_year=data.start_year,
        end_year=data.end_year,
        gpa=data.gpa,
        gpa_scale=data.gpa_scale,
        activities=data.activities,
        sort_order=data.sort_order,
    )
    created = await repo.create(entry)
    await db.commit()
    return EducationResponse.model_validate(created)


@router.put("/education/{edu_id}", response_model=EducationResponse)
async def update_education(
    edu_id: str,
    data: EducationUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    repo = EducationRepository(db)
    entry = await repo.get_by_id(uuid.UUID(edu_id))
    if not entry or str(entry.user_id) != user_id:
        raise HTTPException(status_code=404, detail="Education not found")

    updates = data.model_dump(exclude_unset=True)
    updated = await repo.update(entry, updates)
    await db.commit()
    return EducationResponse.model_validate(updated)


@router.delete("/education/{edu_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_education(
    edu_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    repo = EducationRepository(db)
    entry = await repo.get_by_id(uuid.UUID(edu_id))
    if not entry or str(entry.user_id) != user_id:
        raise HTTPException(status_code=404, detail="Education not found")
    await repo.delete(entry)
    await db.commit()


@router.put("/education", response_model=EducationListResponse)
async def bulk_save_educations(
    data: list[EducationCreate],
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Replace all education entries for the user (used by onboarding)."""
    repo = EducationRepository(db)
    await repo.delete_all_for_user(uuid.UUID(user_id))
    entries = []
    for i, item in enumerate(data):
        entry = Education(
            user_id=uuid.UUID(user_id),
            degree=item.degree,
            custom_degree=item.custom_degree if item.degree == "Other" else None,
            field_of_study=item.field_of_study,
            custom_field=item.custom_field if item.field_of_study == "Other" else None,
            institution=item.institution,
            start_year=item.start_year,
            end_year=item.end_year,
            gpa=item.gpa,
            gpa_scale=item.gpa_scale,
            activities=item.activities,
            sort_order=i,
        )
        created = await repo.create(entry)
        entries.append(created)
    await db.commit()
    return EducationListResponse(
        educations=[EducationResponse.model_validate(e) for e in entries],
        total=len(entries),
    )
