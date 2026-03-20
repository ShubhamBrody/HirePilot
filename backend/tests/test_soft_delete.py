"""
E2E Tests — Soft-Delete & Trash System

Tests:
1. Soft-delete an application, job, resume, recruiter via DELETE endpoints
2. Verify soft-deleted items don't appear in normal list endpoints
3. Trash list returns soft-deleted items
4. Restore from trash
5. Permanent delete from trash
6. Empty trash
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

pytestmark = pytest.mark.asyncio


class TestSoftDeleteApplication:
    """Soft-delete lifecycle for applications."""

    async def test_delete_removes_from_list(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        job = await factory.create_job(db_session, test_user.id)
        resume = await factory.create_resume(db_session, test_user.id)
        app = await factory.create_application(db_session, test_user.id, job.id, resume.id)
        await db_session.commit()

        # Delete the application
        resp = await client.delete(f"/api/v1/applications/{app.id}", headers=auth_headers)
        assert resp.status_code == 204

        # Should not appear in normal list
        resp = await client.get("/api/v1/applications", headers=auth_headers)
        assert resp.status_code == 200
        ids = [a["id"] for a in resp.json()["applications"]]
        assert str(app.id) not in ids

    async def test_deleted_app_appears_in_trash(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        job = await factory.create_job(db_session, test_user.id)
        resume = await factory.create_resume(db_session, test_user.id)
        app = await factory.create_application(db_session, test_user.id, job.id, resume.id)
        await db_session.commit()

        await client.delete(f"/api/v1/applications/{app.id}", headers=auth_headers)

        resp = await client.get("/api/v1/trash?item_type=application", headers=auth_headers)
        assert resp.status_code == 200
        ids = [item["id"] for item in resp.json()["application"]["items"]]
        assert str(app.id) in ids


class TestSoftDeleteJob:
    """Soft-delete lifecycle for jobs."""

    async def test_delete_job(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        job = await factory.create_job(db_session, test_user.id)
        await db_session.commit()

        resp = await client.delete(f"/api/v1/jobs/{job.id}", headers=auth_headers)
        assert resp.status_code == 204

        resp = await client.get("/api/v1/jobs", headers=auth_headers)
        assert resp.status_code == 200
        ids = [j["id"] for j in resp.json()["jobs"]]
        assert str(job.id) not in ids


class TestSoftDeleteRecruiter:
    """Soft-delete lifecycle for recruiters."""

    async def test_delete_recruiter(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        rec = await factory.create_recruiter(db_session, test_user.id)
        await db_session.commit()

        resp = await client.delete(f"/api/v1/recruiters/{rec.id}", headers=auth_headers)
        assert resp.status_code == 204

        resp = await client.get("/api/v1/recruiters", headers=auth_headers)
        assert resp.status_code == 200
        ids = [r["id"] for r in resp.json()["recruiters"]]
        assert str(rec.id) not in ids


class TestTrashRestore:
    """Restore items from trash."""

    async def test_restore_application(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        job = await factory.create_job(db_session, test_user.id)
        resume = await factory.create_resume(db_session, test_user.id)
        app = await factory.create_application(db_session, test_user.id, job.id, resume.id)
        await db_session.commit()

        # Soft-delete
        await client.delete(f"/api/v1/applications/{app.id}", headers=auth_headers)

        # Restore
        resp = await client.post(
            f"/api/v1/trash/application/{app.id}/restore", headers=auth_headers
        )
        assert resp.status_code == 200

        # Should be back in normal list
        resp = await client.get("/api/v1/applications", headers=auth_headers)
        ids = [a["id"] for a in resp.json()["applications"]]
        assert str(app.id) in ids

    async def test_restore_nonexistent_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ):
        fake_id = str(uuid.uuid4())
        resp = await client.post(
            f"/api/v1/trash/application/{fake_id}/restore", headers=auth_headers
        )
        assert resp.status_code == 404


class TestTrashPermanentDelete:
    """Permanently delete items from trash."""

    async def test_permanent_delete_application(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        job = await factory.create_job(db_session, test_user.id)
        resume = await factory.create_resume(db_session, test_user.id)
        app = await factory.create_application(db_session, test_user.id, job.id, resume.id)
        await db_session.commit()

        # Soft-delete
        await client.delete(f"/api/v1/applications/{app.id}", headers=auth_headers)

        # Permanently delete
        resp = await client.delete(
            f"/api/v1/trash/application/{app.id}", headers=auth_headers
        )
        assert resp.status_code == 204

        # Should not be in trash anymore
        resp = await client.get("/api/v1/trash?item_type=application", headers=auth_headers)
        ids = [item["id"] for item in resp.json()["application"]["items"]]
        assert str(app.id) not in ids


class TestTrashEmpty:
    """Empty all trash."""

    async def test_empty_trash(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        job = await factory.create_job(db_session, test_user.id)
        resume = await factory.create_resume(db_session, test_user.id)
        app = await factory.create_application(db_session, test_user.id, job.id, resume.id)
        rec = await factory.create_recruiter(db_session, test_user.id)
        await db_session.commit()

        # Soft-delete both
        await client.delete(f"/api/v1/applications/{app.id}", headers=auth_headers)
        await client.delete(f"/api/v1/recruiters/{rec.id}", headers=auth_headers)

        # Empty trash
        resp = await client.delete("/api/v1/trash", headers=auth_headers)
        assert resp.status_code == 200

        # Trash should be empty
        resp = await client.get("/api/v1/trash", headers=auth_headers)
        data = resp.json()
        total = sum(v["count"] for v in data.values())
        assert total == 0
