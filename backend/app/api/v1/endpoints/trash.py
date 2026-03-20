"""
Trash Endpoints — View, restore, and permanently delete soft-deleted items.
Items are automatically purged after 20 days by a Celery Beat task.
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.repositories.application_repo import ApplicationRepository
from app.repositories.job_repo import JobRepository
from app.repositories.recruiter_repo import RecruiterRepository
from app.repositories.resume_repo import ResumeRepository

router = APIRouter()

ItemType = Literal["application", "job", "resume", "recruiter"]

REPO_MAP = {
    "application": ApplicationRepository,
    "job": JobRepository,
    "resume": ResumeRepository,
    "recruiter": RecruiterRepository,
}


def _get_repo(item_type: ItemType, db: AsyncSession):
    repo_class = REPO_MAP[item_type]
    return repo_class(db)


@router.get("")
async def list_trash(
    item_type: ItemType | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List all soft-deleted items, optionally filtered by type."""
    uid = uuid.UUID(user_id)
    results = {}

    types_to_query = [item_type] if item_type else list(REPO_MAP.keys())

    for t in types_to_query:
        repo = _get_repo(t, db)
        items = await repo.get_deleted(
            filters={"user_id": uid}, skip=skip, limit=limit
        )
        count = await repo.count_deleted(filters={"user_id": uid})
        results[t] = {
            "items": [
                {
                    "id": str(item.id),
                    "type": t,
                    "deleted_at": item.deleted_at.isoformat() if item.deleted_at else None,
                    **_item_summary(t, item),
                }
                for item in items
            ],
            "count": count,
        }

    return results


def _item_summary(item_type: str, item) -> dict:
    """Return a small summary dict appropriate for the item type."""
    if item_type == "application":
        return {"company": item.company, "role": item.role, "status": item.status.value if hasattr(item.status, "value") else str(item.status)}
    if item_type == "job":
        return {"title": item.title, "company": item.company}
    if item_type == "resume":
        return {"name": item.name, "is_master": item.is_master}
    if item_type == "recruiter":
        return {"name": item.name, "company": item.company}
    return {}


@router.post("/{item_type}/{item_id}/restore", status_code=status.HTTP_200_OK)
async def restore_item(
    item_type: ItemType,
    item_id: str,
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
):
    """Restore a soft-deleted item from the trash."""
    repo = _get_repo(item_type, db)
    item = await repo.get_by_id_including_deleted(uuid.UUID(item_id))
    if not item or item.deleted_at is None:
        raise HTTPException(status_code=404, detail="Item not found in trash")
    await repo.restore(item)
    await db.commit()
    return {"message": f"{item_type.title()} restored", "id": item_id}


@router.delete("/{item_type}/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def permanently_delete_item(
    item_type: ItemType,
    item_id: str,
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete a single item from the trash."""
    repo = _get_repo(item_type, db)
    item = await repo.get_by_id_including_deleted(uuid.UUID(item_id))
    if not item or item.deleted_at is None:
        raise HTTPException(status_code=404, detail="Item not found in trash")
    await repo.delete(item)
    await db.commit()


@router.delete("", status_code=status.HTTP_200_OK)
async def empty_trash(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete all items in the trash for the current user."""
    uid = uuid.UUID(user_id)
    total_deleted = 0
    for t in REPO_MAP:
        repo = _get_repo(t, db)
        items = await repo.get_deleted(filters={"user_id": uid}, limit=10000)
        for item in items:
            await repo.delete(item)
            total_deleted += 1
    await db.commit()
    return {"message": f"Permanently deleted {total_deleted} items"}
